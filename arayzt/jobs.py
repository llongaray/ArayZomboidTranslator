"""Pipeline resumível, cancelável e com exportação transacional da tradução."""
from __future__ import annotations
import csv, hashlib, json, os, threading
from collections import Counter
from pathlib import Path
from .core import audit, select_rows, export_overlay, tokens, write_json
from .ollama import OllamaClient, translate_rows
from .summary import summarize

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
    def run(self,game,work,mode='all',model='gemma3:4b',batch=8,url='http://127.0.0.1:11434',translate=False,files='',limit=0):
        if batch<1 or batch>32:raise ValueError('Lote deve estar entre 1 e 32')
        if limit<0:raise ValueError('Limite não pode ser negativo')
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
        approved=[];pending=[];skipped=0
        for row in queue:
            key=fingerprint(row);existing=memory.get(key)
            if isinstance(existing,str) and existing.strip() and tokens(row['en'])==tokens(existing):
                approved.append({'file':row['file'],'key':row['key'],'translation':existing,'source':row['status']});skipped+=1
            else:pending.append(row)
        self.update(phase='translate',total=len(queue),progress=skipped,accepted=skipped,failed=0,message='Traduzindo lotes com checkpoint')
        client=OllamaClient(url,model);errors=[]
        for start in range(0,len(pending),batch):
            if self.cancel.is_set():break
            current=pending[start:start+batch]
            done,failed=translate_rows(client,current,batch_size=batch,retries=1)
            for item in done:
                r=next(r for r in current if r['file']==item['file'] and r['key']==item['key'])
                memory[fingerprint(r)]=item['translation']
            approved.extend(done);errors.extend(failed)
            atomic_json(checkpoint,memory)
            self.update(phase='translate',progress=skipped+start+len(current),total=len(queue),accepted=len(approved),failed=len(errors),message=f'Lote {start//batch+1} concluído')
        # Mesmo se cancelado, exporta somente traduções já validadas em pasta separada.
        self.update(phase='export',message='Validando e exportando arquivos')
        accepted_path=work/'accepted.json';atomic_json(accepted_path,{'translations':approved,'failed':errors,'cancelled':self.cancel.is_set()})
        exported=export_overlay(report,approved,work/'export',work/'backup') if approved else {'translated':0,'files':0,'output':str(work/'export')}
        result.update(exported);result.update({'failed':len(errors),'accepted':str(accepted_path),'checkpoint':str(checkpoint),'cancelled':self.cancel.is_set(),'processed':len(approved)+len(errors),'reused':skipped})
        self.update(phase='done',message='Cancelado parcialmente' if self.cancel.is_set() else 'Concluído')
        return result
