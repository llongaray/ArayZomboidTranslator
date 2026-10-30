import threading
from arayzt import staged_pipeline

def test_queue_depths_follow_stages(monkeypatch):
    started=threading.Event()
    release=threading.Event()
    def translate(client, rows, **kwargs):
        started.set()
        release.wait(2)
        return [{'translation':'Traduzido'}], []
    monkeypatch.setattr(staged_pipeline,'translate_rows',translate)
    monkeypatch.setattr(staged_pipeline,'validate_candidate',lambda *a:('approved', []))
    snapshots=[]
    outputs=[]
    rows=[{'file':'UI_PTBR.txt','key':str(i),'en':'English text','status':'missing'} for i in range(4)]
    def run():
        staged_pipeline.orchestrate_pipeline(
            rows,'http://127.0.0.1:11434','gemma3:4b',1,
            threading.Event(),outputs.append,on_queue=lambda q:snapshots.append(dict(q)))
    thread=threading.Thread(target=run)
    thread.start()
    assert started.wait(2)
    assert any(q['translator']>=3 for q in snapshots)
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert len(outputs)==4
    assert all(set(q)=={'translator','supervisor','manager','orchestrator','delivery'} for q in snapshots)
    assert any(q['supervisor']>=1 or q['manager']>=1 for q in snapshots)
