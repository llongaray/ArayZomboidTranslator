"""Resilient staged multi-agent pipeline: translation, validation, management.

Separate queues allow overlapping stages. All jobs get exactly one terminal
outcome; stage callback failures never kill workers. Infrastructure failures are
reported separately from content-quality failures and do not trigger LLM retries.
"""
from __future__ import annotations

from queue import Queue, Empty
from threading import Thread, Lock, Event
import time
from .agents import manager_decision, MAX_CYCLES
from .ollama import OllamaClient, translate_rows
from .validation import validate_candidate

def orchestrate_pipeline(rows, url, model, workers, cancel, on_result, on_stage=None):
    workers = max(1, min(int(workers), 4))
    if not rows:
        return
    translation, supervision, management = Queue(), Queue(), Queue()
    state_lock = Lock()
    pending = {i: row for i, row in enumerate(rows)}
    fatal = []
    inflight = Event()
    inflight.set()

    def emit(slot, job, stage, detail=None):
        if on_stage is not None:
            try:
                on_stage(slot, job["row"], stage, job["cycle"], detail or {})
            except Exception:
                # Telemetry is best-effort and must never terminate a worker.
                pass

    def finish(job, status, reasons):
        job_id = job["id"]
        with state_lock:
            if job_id not in pending:
                return
            del pending[job_id]
            if not pending:
                inflight.clear()
        result = {
            "row": job["row"], "status": status, "translation": job.get("candidate", ""),
            "reasons": reasons, "attempts": job["cycle"], "history": job["history"]
        }
        try:
            on_result(result)
        except Exception as exc:
            with state_lock:
                fatal.append(exc)
        finally:
            emit(job.get("slot", 0), job, "complete", {"status": status})

    def infrastructure_error(exc):
        # Network errors and service outages must not turn into human review.
        from urllib.error import URLError, HTTPError
        return isinstance(exc, (URLError, HTTPError, TimeoutError, ConnectionError, OSError))

    def translator(slot):
        try:
            client = OllamaClient(url, model)
        except Exception as exc:
            with state_lock:
                fatal.append(exc)
            cancel.set()
            return
        while True:
            try:
                job = translation.get(timeout=.2)
            except Empty:
                if not inflight.is_set():
                    return
                continue
            try:
                if cancel.is_set():
                    finish(job, "cancelled", ["cancelled"])
                    continue
                job["slot"] = slot
                emit(slot, job, "translator")
                req = dict(job["row"])
                if job["feedback"]:
                    req["manager_feedback"] = job["feedback"]
                    req["previous_translation"] = job.get("candidate", "")
                try:
                    out, errors = translate_rows(client, [req], batch_size=1, retries=0)
                    if not out:
                        reason = "; ".join(str(e.get("error", "ollama_error")) for e in errors)
                        # Returned errors may be transport errors represented as text.
                        if any(word in reason.lower() for word in
                               ("timed out", "connection", "refused", "urlerror", "http error", "unreachable")):
                            raise ConnectionError(reason)
                        job["candidate"] = ""
                        job["fault"] = [reason or "ollama_error"]
                    else:
                        job["candidate"] = out[0]["translation"]
                        job["fault"] = []
                except Exception as exc:
                    if infrastructure_error(exc):
                        with state_lock:
                            fatal.append(exc)
                        cancel.set()
                        finish(job, "cancelled", ["ollama_unavailable"])
                        continue
                    job["candidate"] = ""
                    job["fault"] = [str(exc)[:250]]
                job["history"].append({"agent": "translator", "cycle": job["cycle"],
                                       "translation": job["candidate"]})
                supervision.put(job)
            except Exception as exc:
                finish(job, "needs_review", ["translator_exception: " + str(exc)[:150]])
            finally:
                translation.task_done()

    def supervisor():
        while True:
            try:
                job = supervision.get(timeout=.2)
            except Empty:
                if not inflight.is_set():
                    return
                continue
            try:
                if cancel.is_set():
                    finish(job, "cancelled", ["cancelled"])
                    continue
                emit(workers+1, job, "supervisor")
                if job["fault"]:
                    status, reasons = "rejected", job["fault"]
                else:
                    status, reasons = validate_candidate(
                        job["row"]["en"], job["candidate"], job["row"]["key"])
                job["status"], job["reasons"] = status, reasons
                job["history"].append({"agent": "supervisor", "cycle": job["cycle"],
                                       "status": status, "reasons": reasons})
                management.put(job)
            except Exception as exc:
                finish(job, "needs_review", ["supervisor_exception: " + str(exc)[:150]])
            finally:
                supervision.task_done()

    def manager():
        while True:
            try:
                job = management.get(timeout=.2)
            except Empty:
                if not inflight.is_set():
                    return
                continue
            try:
                if cancel.is_set():
                    finish(job, "cancelled", ["cancelled"])
                    continue
                emit(workers+2, job, "manager")
                decision = manager_decision(job["status"], job["reasons"], job["cycle"])
                job["history"].append({"agent": "manager", "cycle": job["cycle"], **decision})
                if decision["decision"] == "approve":
                    finish(job, "approved", [])
                elif decision["decision"] == "retry" and job["cycle"] < MAX_CYCLES:
                    job["feedback"] = decision["context"]
                    job["cycle"] += 1
                    translation.put(job)
                else:
                    finish(job, "needs_review", job["reasons"])
            except Exception as exc:
                finish(job, "needs_review", ["manager_exception: " + str(exc)[:150]])
            finally:
                management.task_done()

    for i, row in enumerate(rows):
        job = {"id": i, "row": row, "cycle": 1, "feedback": "", "candidate": "",
               "fault": [], "history": []}
        if row.get("status") in ("identical", "placeholder_mismatch") and row.get("ptbr"):
            job["candidate"] = row["ptbr"]
            supervision.put(job)
        else:
            translation.put(job)

    threads = [Thread(target=translator, args=(i,), name=f"translator-{i}", daemon=True)
               for i in range(1, workers+1)]
    threads += [Thread(target=supervisor, name="supervisor", daemon=True),
                Thread(target=manager, name="manager", daemon=True)]
    for thread in threads:
        thread.start()

    # Watchdog: never wait forever when every worker of a stage exits unexpectedly.
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
                        "candidate": ""}, "needs_review", ["workers_unavailable"])
            break

    for t in threads:
        t.join(timeout=2)
    if fatal:
        raise RuntimeError("Falha de infraestrutura ou persistência durante processamento: "
                           + str(fatal[0])) from fatal[0]
