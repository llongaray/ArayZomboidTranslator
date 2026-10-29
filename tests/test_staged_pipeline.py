import threading
import time
from arayzt import staged_pipeline

def test_supervisor_runs_while_translator_handles_other_entry(monkeypatch):
    translate_second=threading.Event()
    supervise_first=threading.Event()
    stages=[]
    def mock_translate(client,rows,batch_size=1,retries=0):
        key=rows[0]['key']
        if key=='B':
            translate_second.set()
            assert supervise_first.wait(3)
        return [{'translation':'Traduzido','file':rows[0]['file'],'key':key}], []
    def fake_validate(en,candidate,key):
        if key=='A':
            supervise_first.set()
            assert translate_second.wait(3)
        return 'approved',[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',mock_translate)
    monkeypatch.setattr(staged_pipeline,'validate_candidate',fake_validate)
    rows=[{'file':'UI_PTBR.txt','key':'A','en':'Original','status':'missing'},
          {'file':'UI_PTBR.txt','key':'B','en':'Original','status':'missing'}]
    out=[]
    staged_pipeline.orchestrate_pipeline(rows,'http://127.0.0.1:11434','model',2,
        threading.Event(),out.append,lambda slot,row,stage,cycle,detail:stages.append((row['key'],stage)))
    assert len(out)==2
    assert all(x['status']=='approved' for x in out)
    assert ('A','supervisor') in stages and ('B','translator') in stages

def test_retry_returns_only_rejected_job_to_translator(monkeypatch):
    counts={}
    def mock_translate(client,rows,batch_size=1,retries=0):
        key=rows[0]['key'];counts[key]=counts.get(key,0)+1
        return [{'translation':'ok' if counts[key]>1 else 'bad','file':rows[0]['file'],'key':key}],[]
    def validate(en,candidate,key):
        return ('approved',[]) if candidate=='ok' else ('rejected',['suspected_english'])
    monkeypatch.setattr(staged_pipeline,'translate_rows',mock_translate)
    monkeypatch.setattr(staged_pipeline,'validate_candidate',validate)
    out=[]
    staged_pipeline.orchestrate_pipeline([{'file':'UI_PTBR.txt','key':'A','en':'Original','status':'missing'}],
       'http://127.0.0.1:11434','model',2,threading.Event(),out.append)
    assert counts['A']==2 and out[0]['status']=='approved'

def test_orchestrator_sends_existing_ptbr_directly_to_supervisor(monkeypatch):
    calls=[]
    def fake_translate(client,rows,batch_size=1,retries=0):
        calls.append(rows[0]['key'])
        return [{'translation':'corrigido'}],[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',fake_translate)
    monkeypatch.setattr(staged_pipeline,'validate_candidate',lambda en,candidate,key:('approved',[]))
    out=[];stages=[]
    staged_pipeline.orchestrate_pipeline([
       {'file':'UI_PTBR.txt','key':'A','en':'Known','ptbr':'Conhecido','status':'identical'},
       {'file':'UI_PTBR.txt','key':'B','en':'New','ptbr':None,'status':'missing'}],
       'http://127.0.0.1:11434','model',2,threading.Event(),out.append,
       lambda slot,row,stage,cycle,detail:stages.append((row['key'],stage)))
    assert calls==['B']
    assert ('A','supervisor') in stages
    assert ('A','translator') not in stages
    assert len(out)==2
