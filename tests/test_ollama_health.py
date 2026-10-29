import io
import json
from urllib.error import URLError

import pytest

from arayzt.ollama import OllamaClient


@pytest.mark.parametrize('model,names,status', [
    ('gemma3:4b', ['gemma3:4b'], 'ready'),
    ('gemma3', ['gemma3:latest'], 'ready'),
    ('gemma3:4b', ['gemma3:12b'], 'model_missing'),
    ('gemma3:4b', [], 'model_missing'),
])
def test_installed_models(monkeypatch, model, names, status):
    def respond(url, timeout):
        assert url.endswith('/api/tags')
        assert timeout == 2
        return io.BytesIO(json.dumps({'models': [{'name': n} for n in names]}).encode())
    monkeypatch.setattr('arayzt.ollama.urlopen', respond)
    result = OllamaClient(model=model, timeout=2).health()
    assert result['status'] == status
    assert result['online']
    assert result['ready'] == (status == 'ready')


def test_offline(monkeypatch):
    def fail(*args, **kwargs):
        raise URLError('connection refused')
    monkeypatch.setattr('arayzt.ollama.urlopen', fail)
    result = OllamaClient(timeout=2).health()
    assert result['status'] == 'offline'
    assert not result['ready']


def test_invalid_response(monkeypatch):
    monkeypatch.setattr('arayzt.ollama.urlopen', lambda *a, **k: io.BytesIO(b'{}'))
    assert OllamaClient().health()['status'] == 'invalid_response'


def test_status_endpoint(monkeypatch):
    from arayzt.web import app
    monkeypatch.setattr('arayzt.ollama.urlopen', lambda *a, **k: io.BytesIO(b'{"models": []}'))
    client = app.test_client()
    response = client.get('/api/ollama/status?model=missing')
    assert response.status_code == 200
    assert response.json['status'] == 'model_missing'
    assert client.get('/api/ollama/status?url=http://example.com:11434').status_code == 400
    assert client.get('/api/ollama/status?url=http://localhost:11434@example.com').status_code == 400
