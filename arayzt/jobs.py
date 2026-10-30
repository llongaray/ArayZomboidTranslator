"""Pipeline resumível, cancelável e com exportação transacional da tradução."""
from __future__ import annotations
import csv, hashlib, json, os, threading, time
from collections import Counter, deque
from pathlib import Path
from .core import audit, select_rows, export_overlay, tokens, write_json, canonical_audit_summary
from .ollama import OllamaClient, translate_rows
from .summary import summarize
from .quality import review
from .validation import validate_candidate
from .agents import orchestrate
from .staged_pipeline import orchestrate_pipeline
from .delivery_audit import provenance, save_delivery_audit

class Cancelled(Exception): pass

def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.flush(); os.fsync(f.fileno())
    temp.replace(path)

def fingerprint(row):
    content=json.dumps([row['file'],row['key'],row['en']],ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def load_memory(path):
    try:
        result=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(result,dict):raise ValueError('Checkpoint precisa ser objeto JSON')
        return result
    except FileNotFoundError:return {}

def write_review_csv(report,path,filters=''):
    from .summary import matches
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['arquivo','chave','estado','ingles','portugues'])
        for r in report['rows']:
            if matches(r,filters):w.writerow([r['file'],r['key'],r['status'],r['en'],r.get('ptbr') or ''])
    return path

class Pipeline:
    def __init__(self, event=None, cancel=None):
        self.event=event or (lambda **kw:None)
        self.cancel=cancel or threading.Event()
    def update(self,**kw):self.event(**kw)
    def run(self,game,work,mode='all',model='gemma3:4b',batch=8,url='http://127.0.0.1:11434',translate=False,files='',limit=0,workers=1):
        if batch<1 or batch>32:raise ValueError('Lote deve estar entre 1 e 32')
        if limit<0:raise ValueError('Limite não pode ser negativo')
        if not 1 <= int(workers) <= 4:raise ValueError('Workers devem estar entre 1 e 4')
        work=Path(work).expanduser().resolve();work.mkdir(parents=True,exist_ok=True)
        self.update(phase='audit',message='Lendo arquivos EN/PTBR')
        report=audit(Path(game));atomic_json(work/'audit.json',report)
        reference=canonical_audit_summary(report)
        atomic_json(work/'en-reference-audit.json',reference)
        selected=select_rows(report,mode,files)
        summary=summarize(report,files,len(selected))
        atomic_json(work/'summary.json',summary)
        write_review_csv(report,work/'review.csv',files)
        result={'en_reference_audit':str(work/'en-reference-audit.json'),'en_reference':{k:v for k,v in reference.items() if k not in ('files','problems')},'audit':str(work/'audit.json'),'summary':str(work/'summary.json'),'review_csv':str(work/'review.csv'),'counts':summary['counts'],'filters':files,'selected':len(selected),'source_files':report['source_files'],'parsed_files':report['parsed_files'],'problems':summary['problems']}
        self.update(phase='audit_done',summary=summary,total=len(selected),progress=0)
        if not translate:return result
        if self.cancel.is_set():raise Cancelled('Operação cancelada antes da tradução')
        if not selected:raise ValueError('Nenhuma tradução elegível no filtro atual')
        queue=selected[:limit] if limit else selected
        checkpoint=work/'checkpoint-v040.json';memory=load_memory(checkpoint)
        approved=[];pending=[];skipped=0;review_items=[];histories=[];invalidated=[]
        from .context_glossary import CURATED
        from .source_rules import reviewed_unchanged
        review_checkpoint=work/'review-checkpoint-v1.json'
        review_memory=load_memory(review_checkpoint)
        prior_path=work/'quality-review.json'
        prior_data=json.loads(prior_path.read_text(encoding='utf-8')) if prior_path.is_file() else {}
        prior_review={(i['file'],i['key']):i for i in prior_data.get('needs_review',[])+prior_data.get('rejected',[])}
        history_path=work/'agent-history.json'
        previous_histories=json.loads(history_path.read_text(encoding='utf-8')) if history_path.is_file() else {}
        previous_history={(i['file'],i['key']):i.get('history',[]) for i in previous_histories.get('items',[])}
        preserved_review=0
        for row in queue:
            # Context-policy migrations must precede glossary/cache shortcuts so
            # the analyst's actual decision and authorship are recorded.
            from .analyst_rules import resolution, POLICY_VERSION
            cached=memory.get(fingerprint(row),{})
            legacy=review_memory.get(fingerprint(row)) or prior_review.get((row['file'],row['key']))
            migrated=isinstance(cached,dict) and any(h.get('agent')=='analyst' and h.get('policy_version')==POLICY_VERSION for h in cached.get('history',[]))
            if (resolution(row['key'],row['en']) and isinstance(legacy,dict)
                    and legacy.get('english')==row['en'] and not migrated):
                legacy={**legacy,'history':legacy.get('history',previous_history.get((row['file'],row['key']),[]))}
                pending.append(dict(row,_analyst_resume=legacy))
                continue
            # Reviewed glossary entries take precedence over old checkpoint guesses.
            candidate=row['en'] if reviewed_unchanged(row['key'],row['en']) else CURATED.get(row['key'])
            if isinstance(cached,dict) and cached.get('quality')=='approved' and cached.get('translation')==candidate:
                candidate=None # Preserve recorded producer/history when the glossary agrees.
            if candidate is not None:
                quality,why=validate_candidate(row['en'],candidate,row['key'])
                if quality=='approved':
                    approved.append({'file':row['file'],'key':row['key'],'translation':candidate,'source':row['status'],'producer':'preset','provider':'reviewed_rules'})
                    memory[fingerprint(row)]={'translation':candidate,'quality':'approved','reasons':['curated'],'producer':'preset','provider':'reviewed_rules'}
                    skipped+=1
                    continue
            key=fingerprint(row)
            cached=memory.get(key)
            cached_value=cached if isinstance(cached,str) else cached.get('translation','') if isinstance(cached,dict) else None
            if cached_value is not None and validate_candidate(row['en'],cached_value,row['key'])[0]=='approved':
                meta={'producer':cached.get('producer','unknown'),'provider':cached.get('provider','')} if isinstance(cached,dict) else {'producer':'unknown','provider':''}
                approved.append({'file':row['file'],'key':row['key'],'translation':cached_value,'source':row['status'],**meta})
                if isinstance(cached,dict) and cached.get('history'):
                    histories.append({'file':row['file'],'key':row['key'],'status':'approved',
                                      'reasons':[],'history':cached['history'],'reused':True})
                skipped+=1
                continue
            old_review=review_memory.get(key) or prior_review.get((row['file'],row['key']))
            if isinstance(old_review,dict) and 'english' not in old_review:
                old_review={**old_review,'english':row['en'],'translation':old_review.get('translation',''),'reasons':old_review.get('reasons',[old_review.get('error','legacy_failure')])}
            if (isinstance(old_review,dict) and old_review.get('english')==row['en']
                    and isinstance(old_review.get('translation'),str)):
                old_review=dict(old_review)
                old_review.setdefault('history',previous_history.get((row['file'],row['key']),[]))
                state,reasons=validate_candidate(row['en'],old_review['translation'],row['key'])
                pending.append(dict(row,_analyst_resume=old_review))
                continue
            existing=memory.get(key)
            if isinstance(existing,(str,dict)):
                value=existing if isinstance(existing,str) else existing.get('translation','')
                state,reasons=validate_candidate(row['en'],value,row['key'])
                if state=='approved':
                    approved.append({'file':row['file'],'key':row['key'],'translation':value,'source':row['status'],
                                     'producer':existing.get('producer','unknown') if isinstance(existing,dict) else 'unknown',
                                     'provider':existing.get('provider','') if isinstance(existing,dict) else ''});skipped+=1
                elif state=='needs_review':
                    pending.append(row) # Reavalia com feedback no ciclo multiagente
                else:
                    invalidated.append({'file':row['file'],'key':row['key'],'reasons':reasons})
                    pending.append(row)
            else:pending.append(row)
        self.update(phase='translate',total=len(queue),progress=skipped+preserved_review,accepted=len(approved),needs_review=0,analyst_pending=0,failed=0,remaining=len(pending),manager_decisions={},message='Traduzindo lotes com checkpoint')
        errors=[]
        done_count=skipped+preserved_review
        checkpoint_dirty=int(bool(skipped))
        review_dirty=int(bool(preserved_review))
        cancelled_count=0
        stages_lock=threading.RLock()
        live_events=deque(maxlen=120)
        event_id=0
        def log_event(agent,action,row=None,cycle=0,reasons=None):
            nonlocal event_id
            event_id+=1
            live_events.append({'id':event_id,'timestamp':time.time(),'agent':agent,
                                'action':action,'file':(row or {}).get('file',''),
                                'key':(row or {}).get('key',''),'cycle':cycle,
                                'reasons':reasons or []})
        if skipped:
            log_event('orchestrator','reused',reasons=[f'{skipped} entradas validadas no glossário/checkpoint'])
        if preserved_review:
            log_event('orchestrator','review_preserved',reasons=[f'{preserved_review} pendências de revisão preservadas, sem repetir inferências'])
        self.update(reused=skipped,preserved_review=preserved_review,agent_recent=histories[-30:],agent_events=list(live_events),cancelled_count=0)
        def receive(out):
            with stages_lock:
                receive_locked(out)
        def receive_locked(out):
            nonlocal done_count,checkpoint_dirty,review_dirty,cancelled_count
            row=out['row']
            status=out['status']
            histories.append({'file':row['file'],'key':row['key'],'status':status,'reasons':out['reasons'],'history':out.get('history',[])})
            if status=='approved':
                if review_memory.pop(fingerprint(row),None) is not None:review_dirty+=1
                approved.append({'file':row['file'],'key':row['key'],'translation':out['translation'],'source':row['status'],**provenance(out.get('history',[]),out['translation'],model)})
            elif status=='analysis_failed':
                review_items.append({'file':row['file'],'key':row['key'],'english':row['en'],'translation':out['translation'],'quality':status,'reasons':out['reasons'],**provenance(out.get('history',[]),out['translation'],model)})
                review_memory[fingerprint(row)]={**review_items[-1],'history':out.get('history',[])}
                review_dirty+=1
            elif status=='cancelled':
                cancelled_count+=1
            elif status=='rejected':
                errors.append({'file':row['file'],'key':row['key'],'english':row['en'],'translation':out['translation'],'error':','.join(out['reasons']),'reasons':out['reasons'],**provenance(out.get('history',[]),out['translation'],model)})
            if out['translation'] and status=='approved':
                memory[fingerprint(row)]={'translation':out['translation'],'quality':status,'reasons':out['reasons'],**provenance(out.get('history',[]),out['translation'],model),'history':out.get('history',[])}
                # Persist in small batches instead of rewriting a large checkpoint
                # for each approved item. A crash reprocesses at most 19 entries.
                checkpoint_dirty+=1
            done_count+=1
            self.update(phase='translate',progress=done_count,total=len(queue),
                        percent=round(100*done_count/len(queue),2),
                        accepted=len(approved),needs_review=0,analyst_pending=0,
                        failed=len(errors),workers=int(workers),
                        agent_recent=histories[-30:],agent_events=list(live_events),
                        manager_decisions=dict(stage_decisions),
                        cancelled_count=cancelled_count,
                        remaining=max(0,len(queue)-done_count),
                        message=f"Resultados registrados: {done_count}/{len(queue)} • {status}")
            if checkpoint_dirty>=20 or review_dirty>=20:
                if checkpoint_dirty:
                    atomic_json(checkpoint,memory)
                    checkpoint_dirty=0
                if review_dirty:
                    atomic_json(review_checkpoint,review_memory)
                    review_dirty=0
        self.update(workers=int(workers),percent=round(100*done_count/len(queue),2),
                    message='Orquestrador distribuindo traduções atômicas')
        active_slots={}
        stage_decisions=Counter()
        def on_stage(slot,row,agent,cycle,detail):
            with stages_lock:
                detail=detail or {}
                if agent in ('terminal','retry'):
                    key=detail.get('status', 'retry')
                    stage_decisions[key]+=1
                if agent in ('complete','idle'):
                    previous=active_slots.get(slot)
                    if (previous and previous['file']==row['file'] and previous['key']==row['key']
                            and previous['cycle']==cycle):
                        active_slots.pop(slot,None)
                elif agent in ('translator','translator_ii','supervisor','manager','analyst'):
                    active_slots[slot]={'worker':slot,'agent':agent,'cycle':cycle,
                                        'file':row['file'],'key':row['key'],'detail':detail}
                    log_event(agent,'started',row,cycle)
                elif agent=='stage_done':
                    log_event(detail.get('from','translator'),detail.get('status','done'),row,cycle,detail.get('reasons'))
                elif agent=='validated':
                    log_event('supervisor',detail.get('status','done'),row,cycle,detail.get('reasons'))
                elif agent=='decision':
                    if detail.get('decision')=='analyze':stage_decisions['analyze']+=1
                    action={'approve':'approved','retry':'retry','human_review':'analyze','reject':'rejected','analyze':'analyze'}.get(detail.get('decision'),'done')
                    log_event('manager',action,row,cycle,[detail['reason']] if detail.get('reason') else [])
                elif agent=='terminal':
                    log_event('orchestrator',detail.get('status','done'),row,cycle,detail.get('reasons'))
                self.update(active_workers=list(active_slots.values()),
                            manager_decisions=dict(stage_decisions),agent_events=list(live_events))
        def on_queue(counts):
            with stages_lock:
                self.update(agent_queues=counts,analyst_pending=counts.get('analyst',0)+sum(w['agent']=='analyst' for w in active_slots.values()))
        try:
            orchestrate_pipeline(pending,url,model,int(workers),self.cancel,receive,
                                 on_stage=on_stage,on_queue=on_queue,batch_size=batch)
        finally:
            if checkpoint_dirty:
                atomic_json(checkpoint,memory)
                checkpoint_dirty=0
            if review_dirty:
                atomic_json(review_checkpoint,review_memory)
            self.update(active_workers=[],agent_queues={})
        # Mesmo se cancelado, exporta somente traduções já validadas em pasta separada.
        self.update(phase='export',message='Validando e exportando arquivos')
        invalidation_path=work/'quality-invalidation.json';atomic_json(invalidation_path,{'items':invalidated})
        history_path=work/'agent-history.json';atomic_json(history_path,{'items':histories})
        accepted_path=work/'accepted.json';atomic_json(accepted_path,{'translations':approved,'needs_review':review_items,'failed':errors,'cancelled':self.cancel.is_set()})
        review_path=work/'analysis-report.json';atomic_json(review_path,{'items':errors,'approved_count':len(approved),'policy_version':2})
        atomic_json(work/'quality-review.json',{'needs_review':[],'rejected':errors,'approved_count':len(approved)})
        csv_path=work/'auditoria-traducao.csv'
        try:
            exported=export_overlay(report,approved,work/'export',work/'backup') if approved else {'translated':0,'files':0,'output':str(work/'export')}
        except (ValueError,OSError) as exc:
            exported={'translated':0,'files':0,'output':str(work/'export'),'export_error':str(exc)}
        export_report=work/'export-diagnostics.json'
        atomic_json(export_report,{'delivery_status':exported.get('delivery_status','error'),
                                   'exported_files':exported.get('files',0),
                                   'blocked_files':exported.get('blocked_files',[]),
                                   'preexisting_warnings':exported.get('preexisting_warnings',[]),
                                   'export_error':exported.get('export_error')})
        delivery_csv=save_delivery_audit(work,report,approved,review_items,errors,histories,exported)
        result['delivery_audit_csv']=str(delivery_csv)
        result['export_diagnostics']=str(export_report)
        result.update(exported);result.update({'failed':len(errors),'accepted':str(accepted_path),'checkpoint':str(checkpoint),'review_checkpoint':str(review_checkpoint),'cancelled':self.cancel.is_set(),'processed':len(queue) if not self.cancel.is_set() else len(approved)+len(review_items)+len(errors),'reused':skipped,'preserved_review':preserved_review,'needs_review':0,'analyst_failed':len(errors),'quality_review':str(review_path),'review_csv':str(csv_path),'agent_history':str(history_path),'quality_invalidation':str(invalidation_path)})
        self.update(phase='export_failed' if exported.get('export_error') else ('export_partial' if exported.get('blocked_files') else 'done'),message=exported.get('export_error') or (f"{len(exported.get('blocked_files',[]))} arquivo(s) bloqueado(s) na validação" if exported.get('blocked_files') else ('Cancelado parcialmente' if self.cancel.is_set() else 'Concluído')))
        return result
