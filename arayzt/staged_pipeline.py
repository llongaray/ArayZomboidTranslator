"""Resilient staged multi-agent pipeline: translation, validation, management.

Separate queues allow overlapping stages. All jobs get exactly one terminal
outcome; stage callback failures never kill workers. Infrastructure failures are
reported separately from content-quality failures and do not trigger LLM retries.
"""
from __future__ import annotations

from queue import Queue, Empty
from threading import Thread, Lock, RLock, Event
import time
from .agents import manager_decision, MAX_CYCLES
from .ollama import OllamaClient, translate_rows
from .validation import validate_candidate
from .core import TOKEN_RE
from .source_rules import reviewed_unchanged
from .analyst import TranslationAnalyst

def orchestrate_pipeline(rows, url, model, workers, cancel, on_result, on_stage=None, on_queue=None, batch_size=1, analyst_factory=None):
    workers = max(1, min(int(workers), 4))
    batch_size = max(1, min(int(batch_size), 4))
    if not rows:
        return
    translation, retranslation, supervision, management, analysis = Queue(), Queue(), Queue(), Queue(), Queue()
    state_lock = Lock()
    telemetry_lock = RLock()
    completion_lock = Lock()
    pending = {i: row for i, row in enumerate(rows)}
    fatal = []
    ollama_unavailable = Event()
    inflight = Event()
    inflight.set()
    def queues():
        # Serialize snapshots with their delivery, so an older queue snapshot
        # cannot overwrite a newer one when several workers publish at once.
        with telemetry_lock:
            if on_queue:
                try:
                    on_queue({'translator': translation.qsize(),
                              'translator_ii': retranslation.qsize(),
                              'supervisor': supervision.qsize(),
                              'manager': management.qsize(),
                              'analyst': analysis.qsize(),
                              'orchestrator': 0, 'delivery': 0})
                except Exception:
                    pass

    def emit(slot, job, stage, detail=None):
        if on_stage is not None:
            try:
                on_stage(slot, job["row"], stage, job["cycle"], {**(detail or {}), "job_id": job["id"]})
            except Exception:
                # Telemetry is best-effort and must never terminate a worker.
                pass

    def finish(job, status, reasons):
        job_id = job["id"]
        # Serialize result persistence and terminal state transitions. Another
        # thread may attempt to cancel this job while its result is being saved.
        with completion_lock:
            with state_lock:
                if job_id not in pending:
                    return
            result = {
                "row": job["row"], "status": status, "translation": job.get("candidate", ""),
                "reasons": reasons, "attempts": job["cycle"], "history": job["history"]
            }
            try:
                emit(workers+3, job, "terminal", {"status": status, "reasons": reasons})
                on_result(result)
            except Exception as exc:
                with state_lock:
                    fatal.append(exc)
                cancel.set()
            finally:
                with state_lock:
                    pending.pop(job_id, None)
                    if not pending:
                        inflight.clear()
                emit(job.get("slot", 0), job, "complete", {"status": status})
                emit(workers+3, job, "idle", {"from": "manager"})

    def infrastructure_error(exc):
        # Network errors and service outages must not turn into human review.
        from urllib.error import URLError, HTTPError
        return isinstance(exc, (URLError, HTTPError, TimeoutError, ConnectionError, OSError))

    def translator(slot):
        # The configured budget covers BOTH translation roles. Any free worker
        # prioritizes a correction, then helps with first-pass translations.
        try:
            client = OllamaClient(url, model)
        except Exception as exc:
            with state_lock:
                fatal.append(exc)
            cancel.set()
            return
        while True:
            try:
                with telemetry_lock:
                    try:
                        job = retranslation.get_nowait()
                        inbox, agent = retranslation, 'translator_ii'
                    except Empty:
                        job = translation.get_nowait()
                        inbox, agent = translation, 'translator'
                    group=[job]
                    # Bound prompt/output size and keep first-pass batches local
                    # to one file. Corrections and long/multiline text stay atomic.
                    if agent=='translator' and len(job['row']['en'])<=160 and '\n' not in job['row']['en']:
                        chars=len(job['row']['en'])
                        while len(group)<batch_size:
                            try:
                                extra=translation.get_nowait()
                            except Empty:
                                break
                            text=extra['row']['en']
                            if (extra['row']['file']!=job['row']['file'] or len(text)>160
                                    or '\n' in text or chars+len(text)>600):
                                translation.put(extra)
                                translation.task_done()
                                break
                            group.append(extra)
                            chars+=len(text)
                    queues()
            except Empty:
                if not inflight.is_set():
                    return
                time.sleep(.02)
                continue
            try:
                if cancel.is_set():
                    for job in group:
                        finish(job, 'cancelled', ['cancelled'])
                    continue
                if ollama_unavailable.is_set():
                    for job in group:
                        job['reasons']=['ollama_unavailable']
                        job['fallback_status']='rejected'
                        job['history'].append({'agent':'orchestrator','cycle':job['cycle'],
                                               'decision':'analyze','reason':'ollama_unavailable'})
                        with telemetry_lock:
                            analysis.put(job)
                            queues()
                    continue
                requests=[]
                tasks=[{'key':j['row']['key'],'file':j['row']['file'],'cycle':j['cycle']} for j in group]
                for job in group:
                    job['slot']=slot
                    emit(slot,job,agent,{'tasks':tasks})
                    req=dict(job['row'])
                    if job['feedback']:
                        req['manager_feedback']=job['feedback']
                        req['previous_translation']=job.get('candidate','')
                    requests.append(req)
                started=time.monotonic()
                try:
                    out,errors=translate_rows(client,requests,batch_size=len(requests),retries=0)
                    faults='; '.join(str(e.get('error','ollama_error')) for e in errors)
                    if not out and any(word in faults.lower() for word in
                            ('timed out','connection','refused','urlerror','http error','unreachable')):
                        raise ConnectionError(faults)
                except Exception as exc:
                    if infrastructure_error(exc):
                        ollama_unavailable.set()
                        for job in group:
                            job['reasons']=['ollama_unavailable',str(exc)[:200]]
                            job['fallback_status']='rejected'
                            job['history'].append({'agent':agent,'cycle':job['cycle'],
                                'status':'failed','translation':'','reasons':job['reasons']})
                            with telemetry_lock:
                                analysis.put(job)
                                queues()
                        continue
                    out=[]
                    errors=[{'file':r['file'],'key':r['key'],'error':str(exc)[:250]} for r in requests]
                by_key={(r.get('file'),r.get('key')):r for r in out}
                errors_by_key={(r.get('file'),r.get('key')):r.get('error','ollama_error') for r in errors}
                for job in group:
                    identity=(job['row']['file'],job['row']['key'])
                    candidate=by_key.get(identity)
                    # Single-entry test/custom clients may omit identity fields.
                    if len(group)==1 and len(out)==1:
                        candidate=out[0]
                    job['candidate']=candidate['translation'] if candidate else ''
                    job['fault']=[] if candidate else [errors_by_key.get(identity,'missing_batch_result')]
                    job['history'].append({'agent':agent,'cycle':job['cycle'],
                                           'translation':job['candidate'],'batch_size':len(group),
                                           'elapsed_seconds':round(time.monotonic()-started,4)})
                    emit(slot,job,'stage_done',{'from':agent,'status':'rejected' if job['fault'] else 'done','reasons':job['fault']})
                    with telemetry_lock:
                        supervision.put(job)
                        queues()
            except Exception as exc:
                for job in group:
                    finish(job,'rejected',['translator_exception: '+str(exc)[:150]])
            finally:
                for job in group:
                    emit(slot,job,'idle',{'from':agent})
                    inbox.task_done()

    def supervisor():
        while True:
            try:
                job = supervision.get(timeout=.2)
                queues()
            except Empty:
                if not inflight.is_set():
                    return
                continue
            try:
                if cancel.is_set():
                    finish(job, "cancelled", ["cancelled"])
                    continue
                emit(workers+2, job, "supervisor")
                if job["fault"]:
                    status, reasons = "rejected", job["fault"]
                else:
                    status, reasons = validate_candidate(
                        job["row"]["en"], job["candidate"], job["row"]["key"])
                job["status"], job["reasons"] = status, reasons
                job["history"].append({"agent": "supervisor", "cycle": job["cycle"],
                                       "status": status, "reasons": reasons})
                emit(workers+2, job, "validated", {"status": status, "reasons": reasons})
                emit(workers+2, job, "idle", {"from": "supervisor"})
                with telemetry_lock:
                    management.put(job)
                    queues()
            except Exception as exc:
                finish(job, "rejected", ["supervisor_exception: " + str(exc)[:150]])
            finally:
                emit(workers+2, job, "idle", {"from": "supervisor"})
                supervision.task_done()

    def manager():
        while True:
            try:
                job = management.get(timeout=.2)
                queues()
            except Empty:
                if not inflight.is_set():
                    return
                continue
            try:
                if cancel.is_set():
                    finish(job, "cancelled", ["cancelled"])
                    continue
                emit(workers+3, job, "manager")
                candidates=[h['translation'] for h in job['history']
                            if h['agent'] in ('translator','translator_ii')]
                decision = manager_decision(job['status'], job['reasons'], job['cycle'],
                    candidate=job['candidate'], previous_candidates=candidates[:-1], row=job['row'])
                if decision['reason']=='no_progress':
                    job['reasons']=list(dict.fromkeys(job['reasons']+['no_progress']))
                if job.get('analyst_attempted') and decision['decision']!='approve':
                    decision={'decision':'reject',
                              'reason':'analyst_unsolved','context':','.join(job['reasons'])}
                elif decision['decision'] in ('analyze','reject') and not any(
                        reason in ('invalid_source','empty_source','nonempty_for_empty_source') for reason in job['reasons']):
                    job['fallback_status']='rejected' if decision['decision']=='reject' else 'needs_review'
                    decision={**decision,'decision':'analyze'}
                job["history"].append({"agent": "manager", "cycle": job["cycle"], **decision})
                emit(workers+3, job, "decision", decision)
                if decision["decision"] == "approve":
                    finish(job, "approved", [])
                elif decision["decision"] == "reject":
                    finish(job, "rejected", job["reasons"])
                elif decision['decision']=='analyze':
                    with telemetry_lock:
                        analysis.put(job)
                        queues()
                elif decision["decision"] == "retry" and job["cycle"] < MAX_CYCLES:
                    job["feedback"] = decision["context"]
                    job["cycle"] += 1
                    emit(workers+3, job, "retry", {"reason": decision.get("reason", "")})
                    with telemetry_lock:
                        retranslation.put(job)
                        queues()
                    emit(workers+3, job, "idle", {"from": "manager", "decision": "retry"})
                else:
                    finish(job, "rejected", job["reasons"])
            except Exception as exc:
                finish(job, "rejected", ["manager_exception: " + str(exc)[:150]])
            finally:
                emit(workers+3, job, "idle", {"from": "manager"})
                management.task_done()

    def analyst_worker():
        analyst=None
        while True:
            try:
                job=analysis.get(timeout=.2)
                queues()
            except Empty:
                if not inflight.is_set():
                    return
                continue
            try:
                if cancel.is_set():
                    finish(job,'cancelled',['cancelled'])
                    continue
                emit(workers+1,job,'analyst')
                job['analyst_attempted']=True
                if analyst is None:
                    analyst=(analyst_factory or TranslationAnalyst)()
                result=analyst.analyze(job['row'],job.get('candidate',''),job.get('reasons',[]))
                if result['status']=='approved':
                    # Presets/providers cannot bypass the shared validation gate.
                    result['status'],result['reasons']=validate_candidate(
                        job['row']['en'],result['translation'],job['row']['key'])
                job['candidate']=result['translation']
                job['status']=result['status']
                job['reasons']=result['reasons']
                job['history'].append({'agent':'analyst','cycle':job['cycle'],**result})
                emit(workers+1,job,'stage_done',{'from':'analyst','status':job['status'],
                     'reasons':job['reasons'],'provider':result.get('provider')})
                with telemetry_lock:
                    management.put(job)
                    queues()
            except Exception as exc:
                job['history'].append({'agent':'analyst','cycle':job['cycle'],'status':'needs_review',
                                       'reasons':['analyst_exception:'+str(exc)[:150]]})
                finish(job,'rejected',['analyst_exception:'+str(exc)[:150]])
            finally:
                emit(workers+1,job,'idle',{'from':'analyst'})
                analysis.task_done()

    for i, row in enumerate(rows):
        job = {"id": i, "row": row, "cycle": 1, "feedback": "", "candidate": "",
               "fault": [], "history": []}
        if row.get('_analyst_resume'):
            previous=row['_analyst_resume']
            job.update(candidate=previous['translation'],reasons=previous.get('reasons',[]),
                       history=list(previous.get('history',[])),fallback_status='needs_review')
            analysis.put(job)
        elif reviewed_unchanged(row['key'],row['en']):
            job['candidate']=row['en']
            supervision.put(job)
        elif row.get("status") in ("identical", "placeholder_mismatch") and row.get("ptbr"):
            job["candidate"] = row["ptbr"]
            supervision.put(job)
        elif row.get("en") and not any(ch.isalpha() for ch in TOKEN_RE.sub("", row["en"])):
            job["candidate"] = row["en"]
            supervision.put(job)
        else:
            translation.put(job)

    threads = [Thread(target=translator, args=(i,), name=f"translator-{i}", daemon=True)
               for i in range(1, workers+1)]
    threads.append(Thread(target=analyst_worker,name='analyst-5',daemon=True))
    threads += [Thread(target=supervisor, name="supervisor", daemon=True),
                Thread(target=manager, name="manager", daemon=True)]
    queues()
    for thread in threads:
        thread.start()

    # Watchdog: stages operate independently; only fatal infrastructure errors stop all work.
    while inflight.is_set():
        time.sleep(.05)
        if cancel.is_set():
            # Flush remaining queue entries as cancelled, including jobs belonging
            # to unexpectedly stopped stages. Finish is idempotent by job ID.
            with state_lock:
                remaining = list(pending.items())
            for i, row in remaining:
                finish({"id": i, "row": row, "cycle": 0, "history": [],
                        "candidate": ""}, "cancelled", ["cancelled"])
            break
        if not any(t.is_alive() for t in threads[:-2]):
            with state_lock:
                remaining = list(pending.items())
            for i, row in remaining:
                finish({"id": i, "row": row, "cycle": 0, "history": [],
                        "candidate": ""}, "rejected", ["workers_unavailable"])
            break

    for t in threads:
        t.join(timeout=2)
    if fatal:
        raise RuntimeError("Falha de infraestrutura ou persistência durante processamento: "
                           + str(fatal[0])) from fatal[0]
