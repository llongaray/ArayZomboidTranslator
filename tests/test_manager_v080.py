from arayzt.agents import manager_decision, translate_atom
import threading
from unittest.mock import patch

def test_manager_feedback():
    d=manager_decision("needs_review",["unchanged_english"],1)
    assert d["decision"]=="retry"
    assert d["context"]

def test_max_cycles():
    assert manager_decision("rejected",["ollama_error"],3)["decision"]=="human_review"

def test_supervisor_retry_cycle():
    row={"file":"UI_PTBR.txt","key":"A","en":"Sleep","status":"missing"}
    calls=[]
    def fake(client,records,**kw):
        calls.append(dict(records[0]))
        return ([{"translation":"Sleep" if len(calls)==1 else "Dormir"}],[])
    with patch("arayzt.agents.translate_rows",side_effect=fake):
        result=translate_atom(row,"http://127.0.0.1:11434","gemma3:4b",threading.Event())
    assert result["status"]=="approved"
    assert len(calls)==2
    assert calls[1]["manager_feedback"]
