import threading
import pytest
from arayzt import staged_pipeline as pipeline

def _rows(n=3):
    return [{'file':'UI_PTBR.txt','key':str(i),'en':'Original','status':'missing'} for i in range(n)]

def test_supervisor_exception_completes_all_jobs(monkeypatch):
    monkeypatch.setattr(pipeline,'translate_rows',lambda client,records,**kw:([{'translation':'Teste'}],[]))
    monkeypatch.setattr(pipeline,'validate_candidate',lambda *args:(_ for _ in ()).throw(ValueError('bad validator')))
    output=[]
    pipeline.orchestrate_pipeline(_rows(), 'http://127.0.0.1:11434','model',3,
                                  threading.Event(),output.append)
    assert len(output)==3
    assert all(x['status']=='needs_review' for x in output)

def test_result_callback_failure_does_not_hang(monkeypatch):
    monkeypatch.setattr(pipeline,'translate_rows',lambda client,records,**kw:([{'translation':'Teste'}],[]))
    monkeypatch.setattr(pipeline,'validate_candidate',lambda *args:('approved',[]))
    def bad_callback(result):
        raise OSError('disk full')
    with pytest.raises(RuntimeError,match='persistência'):
        pipeline.orchestrate_pipeline(_rows(), 'http://127.0.0.1:11434','model',2,
                                      threading.Event(),bad_callback)

def test_ollama_connection_failure_not_human_review(monkeypatch):
    def offline(client,records,**kw):
        raise ConnectionError('connection refused')
    monkeypatch.setattr(pipeline,'translate_rows',offline)
    results=[]
    with pytest.raises(RuntimeError,match='infraestrutura'):
        pipeline.orchestrate_pipeline(_rows(), 'http://127.0.0.1:11434','model',2,
                                      threading.Event(),results.append)
    assert all(x['status']=='cancelled' for x in results)
