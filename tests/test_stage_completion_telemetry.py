import threading
from arayzt import staged_pipeline

def test_every_manager_terminal_decision_emits_result_and_clears_agent_slot(monkeypatch):
    def fake_translate(client,rows,**kwargs):
        return [{'translation':'Tradução segura'}], []
    monkeypatch.setattr(staged_pipeline,'translate_rows',fake_translate)
    monkeypatch.setattr(staged_pipeline,'validate_candidate',lambda *args: ('approved',[]))
    events=[];results=[]
    rows=[{'file':'UI_PTBR.txt','key':f'UI_{i}','en':'Source','status':'missing'} for i in range(15)]
    staged_pipeline.orchestrate_pipeline(
        rows,'http://127.0.0.1:11434','fake',4,threading.Event(),
        results.append,
        lambda slot,row,stage,cycle,detail:events.append((slot,row['key'],stage)))
    assert len(results)==len(rows)
    assert all(r['status']=='approved' for r in results)
    assert len({r['row']['key'] for r in results})==len(rows)
    assert len([e for e in events if e[2]=='complete'])==len(rows)
    assert any(e[2]=='idle' for e in events)
    active={}
    for slot,key,stage in events:
        if stage in ('idle','complete'):
            if active.get(slot)==key:
                active.pop(slot,None)
        else:
            active[slot]=key
    assert active=={}

def test_rework_produces_only_one_terminal_result(monkeypatch):
    calls={}
    def fake_translate(client,rows,**kwargs):
        key=rows[0]['key']
        calls[key]=calls.get(key,0)+1
        return [{'translation':'Bom' if calls[key]>1 else 'Bad'}],[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',fake_translate)
    monkeypatch.setattr(staged_pipeline,'validate_candidate',
                        lambda source,candidate,key:('approved',[]) if candidate=='Bom' else ('rejected',['placeholder_mismatch']))
    output=[];events=[]
    staged_pipeline.orchestrate_pipeline(
        [{'file':'UI_PTBR.txt','key':'X','en':'Good','status':'missing'}],
        'http://127.0.0.1:11434','fake',2,threading.Event(),output.append,
        lambda slot,row,stage,cycle,detail:events.append((stage,cycle)))
    assert len(output)==1 and output[0]['status']=='approved'
    assert ('translator_ii',2) in events
