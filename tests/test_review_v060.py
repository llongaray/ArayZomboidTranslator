from arayzt.manual_review import decision_id
from arayzt.validation import validate_candidate

def test_decision_id_unique():
    assert decision_id("UI_PTBR.txt","x") != decision_id("ContextMenu_PTBR.txt","x")

def test_json_metadata_blocked():
    assert validate_candidate("Hello", '{"file":"UI_PTBR.txt","key":"hello"}', "hello")[0]=="rejected"
