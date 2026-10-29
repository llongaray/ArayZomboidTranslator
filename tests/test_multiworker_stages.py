from arayzt import agents
import threading, time

def test_workers_overlap_and_report_separate_stages(monkeypatch):
    barrier=threading.Barrier(3,timeout=3)
    visited=[];lock=threading.Lock()
    def fake_atom(row,url,model,cancel,on_stage=None,worker_id=None):
        on_stage(worker_id,row,'translator',1,{})
        barrier.wait()
        with lock:visited.append(worker_id)
        on_stage(worker_id,row,'supervisor',1,{})
        on_stage(worker_id,row,'manager',1,{})
        return {'row':row,'status':'approved','translation':'OK','attempts':1,'history':[]}
    monkeypatch.setattr(agents,'translate_atom',fake_atom)
    rows=[{'file':'UI_PTBR.txt','key':str(i),'en':str(i)} for i in range(3)]
    events=[];results=[]
    agents.orchestrate(rows,'local','model',3,threading.Event(),results.append,
                       lambda worker,row,stage,cycle,detail:events.append((worker,stage)))
    assert len(results)==3
    assert set(visited)=={1,2,3}
    assert {(i,'translator') for i in (1,2,3)}.issubset(set(events))
    assert len([e for e in events if e[1]=='complete'])==3
