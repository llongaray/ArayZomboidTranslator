import threading
from arayzt import staged_pipeline

def test_retry_uses_translator_ii(monkeypatch):
    calls=[]
    def translate(client, rows, **kw):
        calls.append(rows[0]['key'])
        return [{'translation': 'final' if len(calls)>1 else 'draft'}], []
    monkeypatch.setattr(staged_pipeline,'translate_rows',translate)
    monkeypatch.setattr(staged_pipeline,'validate_candidate',lambda en,val,key: ('approved',[]) if val=='final' else ('rejected',['placeholder_mismatch']))
    events=[];out=[]
    staged_pipeline.orchestrate_pipeline([{'file':'UI_PTBR.txt','key':'X','en':'Original','status':'missing'}], 'http://127.0.0.1:11434','test',2,threading.Event(),out.append,lambda slot,row,agent,cycle,detail:events.append((agent,cycle)))
    assert len(out)==1 and out[0]['status']=='approved'
    assert ('translator',1) in events and ('translator_ii',2) in events
    assert ('translator',2) not in events
