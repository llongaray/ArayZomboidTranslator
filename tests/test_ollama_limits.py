"""Regression checks for bounded Ollama requests and safe cancellation."""
from pathlib import Path
from unittest.mock import patch
from arayzt.ollama import OllamaClient

def test_ollama_timeout_is_bounded():
    assert OllamaClient().timeout == 35

def test_ollama_resource_limits():
    import json
    from unittest.mock import MagicMock
    fake=MagicMock()
    fake.__enter__.return_value=fake
    fake.__exit__.return_value=False
    fake.read.return_value=b'{"response":"{\\\"translations\\\":{\\\"k0\\\":\\\"Ola\\\"}}"}'
    sample=[{'key_id':'k0','file':'UI_PTBR.txt','key':'A','en':'Hello','status':'missing'}]
    with patch('arayzt.ollama.urlopen',return_value=fake) as opened:
        try:OllamaClient().generate(sample)
        except (ValueError,TypeError):pass
        args=opened.call_args
        assert args.kwargs['timeout']==35
        payload=json.loads(args.args[0].data)
        assert payload['options']['num_ctx']==4096
        assert payload['options']['num_predict']==768
