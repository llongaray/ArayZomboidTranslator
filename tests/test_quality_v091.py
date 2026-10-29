from arayzt.quality import review
from arayzt.validation import validate_lua_comparative
from arayzt.agents import translate_atom
import threading

def test_agent_feedback_rejected():
    assert review("Roe","GERENTE: Roe","ContextMenu_FoodType_Roe")[0]=="rejected"

def test_semantic_moodle_mismatch():
    state,reasons=review("Thirsty","Com fome","Moodles_Thirst_lvl1")
    assert state=="needs_review"
    assert "semantic_thirst_hunger" in reasons

def test_unrestored_marker_rejected():
    assert review("Bandage","⟦Bandagem⟧")[0]=="rejected"

def test_invariant_values():
    assert review("100%","100%")[0]=="approved"
    assert review("Xbox","Xbox")[0]=="approved"
    assert translate_atom({"file":"UI_PTBR.txt","key":"Percentage","en":"100%","status":"missing"},"http://127.0.0.1:11434","gemma3:4b",threading.Event())["status"]=="approved"

def test_empty_source_escalated():
    assert review("","Manager instructions")[0]=="rejected"

def test_preexisting_lua_warning_not_new(tmp_path):
    source=tmp_path/"UI_PTBR.txt"
    out=tmp_path/"result.txt"
    text='UI_PTBR = {\n  A = "Ok",\n  Unparsed = os.getenv("TEST"),\n}\n'
    source.write_text(text,encoding="utf-8")
    out.write_text(text,encoding="utf-8")
    result=validate_lua_comparative(out,source,{})
    assert result["preexisting"]
    assert not result["introduced"]
