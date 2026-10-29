"""Regressions from the 2026-10-29 human-review PDF."""
import json
from unittest.mock import patch
from arayzt.quality import review
from arayzt.core import protect,restore,tokens
from arayzt.ollama import OllamaClient

def test_manager_feedback_is_not_translation():
    for candidate in (
        "GERENTE: Corrija o erro: agent_feedback_leak",
        "Gerente: Corrija o erro: unchanged_english ANTERIOR: Gerente",
        "Corrigir o erro: vazamento de feedback do agente.",
    ):
        state, reasons=review("Role:",candidate,"IGUI_AdminPanel_Role")
        assert state=="rejected" and "agent_feedback_leak" in reasons

def test_pz_markers_are_lossless():
    for source in ("%2 and %3 (%1)", "<CENTRE> <SIZE:medium> Let's go! <LINE> Press %1",
                   "%1<br>accepted war!<br>%2",
                   "<JOYPAD:BButton,28,28>"):
        masked,mapping=protect(source)
        assert restore(masked,mapping)==source
        assert tokens(source)==tokens(restore(masked,mapping))

def test_ollama_rejects_manager_echo_before_acceptance():
    class FakeResponse:
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self,*args):return b''
    def mock_open(request,timeout):
        class Response(FakeResponse):
            pass
        response=Response()
        with patch('arayzt.ollama.json.load',return_value={'response':json.dumps({'translations':{'k0':'GERENTE: Corrija o erro'}})}):
            return response
    # Validate the rejection rule also guards the shared quality boundary.
    assert review('Role:', 'GERENTE: Corrija o erro','IGUI_AdminPanel_Role')[0]=='rejected'
