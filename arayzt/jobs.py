"""Pipeline resumível, cancelável e com exportação transacional da tradução."""
from __future__ import annotations
import csv, hashlib, json, os, threading, time
from collections import Counter
from pathlib import Path
from .core import audit, select_rows, export_overlay, tokens, write_json
from .ollama import OllamaClient, translate_rows
from .summary import summarize
from .quality import review
from .validation import validate_candidate
from .manual_review import read_decisions
from .agents import orchestrate

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
        selected=select_rows(report,mode,files)
        summary=summarize(report,files,len(selected))
        atomic_json(work/'summary.json',summary)
        write_review_csv(report,work/'review.csv',files)
        result={'audit':str(work/'audit.json'),'summary':str(work/'summary.json'),'review_csv':str(work/'review.csv'),'counts':summary['counts'],'filters':files,'selected':len(selected),'source_files':report['source_files'],'parsed_files':report['parsed_files'],'problems':summary['problems']}
        self.update(phase='audit_done',summary=summary,total=len(selected),progress=0)
        if not translate:return result
        if self.cancel.is_set():raise Cancelled('Operação cancelada antes da tradução')
        if not selected:raise ValueError('Nenhuma tradução elegível no filtro atual')
        queue=selected[:limit] if limit else selected
        checkpoint=work/'checkpoint-v040.json';memory=load_memory(checkpoint)
        approved=[];pending=[];skipped=0;review_items=[];histories=[];invalidated=[]
        from .context_glossary import CURATED
        for row in queue:
            # Reviewed glossary entries take precedence over old checkpoint guesses.
            if row['key'] in CURATED:
                candidate=CURATED[row['key']]
                quality,why=validate_candidate(row['en'],candidate,row['key'])
                if quality=='approved':
                    approved.append({'file':row['file'],'key':row['key'],'translation':candidate,'source':row['status']})
                    memory[fingerprint(row)]={'translation':candidate,'quality':'approved','reasons':['curated']}
                    skipped+=1
                    continue
            key=fingerprint(row);existing=memory.get(key)
            if isinstance(existing,(str,dict)):
                value=existing if isinstance(existing,str) else existing.get('translation','')
                state,reasons=validate_candidate(row['en'],value,row['key'])
                if state=='approved':
                    approved.append({'file':row['file'],'key':row['key'],'translation':value,'source':row['status']});skipped+=1
                elif state=='needs_review':
                    pending.append(row) # Reavalia com feedback no ciclo multiagente
                else:
                    invalidated.append({'file':row['file'],'key':row['key'],'reasons':reasons})
                    pending.append(row)
            else:pending.append(row)
        self.update(phase='translate',total=len(queue),progress=skipped,accepted=len(approved),needs_review=len(review_items),failed=0,message='Traduzindo lotes com checkpoint')
        errors=[]
        done_count=skipped
        def receive(out):
            nonlocal done_count
            row=out['row']
            status=out['status']
            histories.append({'file':row['file'],'key':row['key'],'status':status,'history':out.get('history',[])})
            self.update(agent_recent=histories[-12:])
            if status=='approved':
                approved.append({'file':row['file'],'key':row['key'],'translation':out['translation'],'source':row['status']})
            elif status=='needs_review':
                review_items.append({'file':row['file'],'key':row['key'],'english':row['en'],'translation':out['translation'],'quality':status,'reasons':out['reasons']})
            elif status=='rejected':
                errors.append({'file':row['file'],'key':row['key'],'error':','.join(out['reasons'])})
            if out['translation'] and status=='approved':
                memory[fingerprint(row)]={'translation':out['translation'],'quality':status,'reasons':out['reasons']}
                # Atomic disk write by orchestrator only; no worker mutates the checkpoint.
                atomic_json(checkpoint,memory)
            done_count+=1
            self.update(phase='translate',progress=done_count,total=len(queue),
                        percent=round(100*done_count/len(queue),2),
                        accepted=len(approved),needs_review=len(review_items),
                        failed=len(errors),workers=int(workers),
                        message=f"Orquestrador: {done_count}/{len(queue)} • Supervisor: {status}")
        self.update(workers=int(workers),percent=round(100*skipped/len(queue),2),
                    message='Orquestrador distribuindo traduções atômicas')
        orchestrate(pending,url,model,int(workers),self.cancel,receive)
        # Manual approvals override only the matching entries in the current queue.
        decisions=read_decisions(work)
        by_key={(r['file'],r['key']):r for r in queue}
        for d in decisions.values():
            identity=(d['file'],d['key'])
            original=by_key.get(identity)
            if original is None:continue
            approved=[r for r in approved if (r['file'],r['key'])!=identity]
            review_items=[r for r in review_items if (r['file'],r['key'])!=identity]
            if d['action']=='approve':
                status,reasons=validate_candidate(original['en'],d['translation'],original['key'])
                if status!='rejected':
                    approved.append({'file':original['file'],'key':original['key'],'translation':d['translation'],'source':original['status'],'review_approved':True})
            else:
                review_items.append({'file':original['file'],'key':original['key'],'english':original['en'],'translation':d['translation'],'quality':'rejected_by_human','reasons':['manual_rejection']})
        # Mesmo se cancelado, exporta somente traduções já validadas em pasta separada.
        self.update(phase='export',message='Validando e exportando arquivos')
        invalidation_path=work/'quality-invalidation.json';atomic_json(invalidation_path,{'items':invalidated})
        history_path=work/'agent-history.json';atomic_json(history_path,{'items':histories})
        accepted_path=work/'accepted.json';atomic_json(accepted_path,{'translations':approved,'needs_review':review_items,'failed':errors,'cancelled':self.cancel.is_set()})
        review_path=work/'quality-review.json';atomic_json(review_path,{'needs_review':review_items,'rejected':errors,'approved_count':len(approved)})
        try:
            exported=export_overlay(report,approved,work/'export',work/'backup') if approved else {'translated':0,'files':0,'output':str(work/'export')}
        except (ValueError,OSError) as exc:
            exported={'translated':0,'files':0,'output':str(work/'export'),'export_error':str(exc)}
        result.update(exported);result.update({'failed':len(errors),'accepted':str(accepted_path),'checkpoint':str(checkpoint),'cancelled':self.cancel.is_set(),'processed':skipped+len(pending) if not self.cancel.is_set() else len(approved)+len(review_items)+len(errors),'reused':skipped,'needs_review':len(review_items),'quality_review':str(review_path),'agent_history':str(history_path),'quality_invalidation':str(invalidation_path)})
        self.update(phase='export_failed' if exported.get('export_error') else ('export_partial' if exported.get('blocked_files') else 'done'),message=exported.get('export_error') or (f"{len(exported.get('blocked_files',[]))} arquivo(s) bloqueado(s) na validação" if exported.get('blocked_files') else ('Cancelado parcialmente' if self.cancel.is_set() else 'Concluído')))
        return result
