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
    assert all(x['status']=='rejected' for x in output)

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
    pipeline.orchestrate_pipeline(_rows(), 'http://127.0.0.1:11434','model',2,
                                  threading.Event(),results.append)
    # The offline analyst receives the outage instead of cancelling other work.
    # In unit tests its model is unavailable, so infrastructure stays a failed
    # result with its cause, not an unexplained language-review verdict.
    assert len(results)==3
    assert all(x['status']=='rejected' for x in results)
    assert all('ollama_unavailable' in x['reasons'] for x in results)
