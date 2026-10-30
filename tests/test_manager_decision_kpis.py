import threading
from arayzt import staged_pipeline

def test_terminal_decisions_are_sent_before_result_persistence(monkeypatch):
    monkeypatch.setattr(staged_pipeline,'translate_rows',
                        lambda client,rows,**kw:([{'translation':'Bom'}],[]))
    monkeypatch.setattr(staged_pipeline,'validate_candidate',
                        lambda *args:('approved',[]))
    events=[];results=[]
    def persist(result):
        assert any(e[0]=='terminal' and e[1]=='approved' for e in events)
        results.append(result)
    staged_pipeline.orchestrate_pipeline(
        [{'file':'UI_PTBR.txt','key':'UI_Test','en':'Good','status':'missing'}],
        'http://127.0.0.1:11434','fake',2,threading.Event(),persist,
        lambda slot,row,stage,cycle,detail:events.append((stage,detail.get('status'))))
    assert len(results)==1 and results[0]['status']=='approved'

def test_rejected_entry_does_not_disappear(monkeypatch):
    monkeypatch.setattr(staged_pipeline,'translate_rows',
                        lambda client,rows,**kw:([{'translation':'Invalid'}],[]))
    monkeypatch.setattr(staged_pipeline,'validate_candidate',
                        lambda *args:('rejected',['structural_echo']))
    results=[]
    staged_pipeline.orchestrate_pipeline(
        [{'file':'UI_PTBR.txt','key':'UI_Test','en':'Good','status':'missing'}],
        'http://127.0.0.1:11434','fake',2,threading.Event(),results.append)
    assert len(results)==1
    assert results[0]['status']=='rejected'
