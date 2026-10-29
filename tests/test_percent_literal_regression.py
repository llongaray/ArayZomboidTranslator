from arayzt.core import tokens
from arayzt.validation import validate_candidate

def test_literal_percent_not_placeholder():
    english = "90% of deaths are caused by taking unnecessary risks."
    pt = "90% das mortes são causadas por riscos desnecessários."
    assert tokens(english) == tokens(pt)
    assert validate_candidate(english, pt, 'UI_quick_tip_joke4')[0] == 'approved'

def test_genuine_tokens_still_preserved():
    assert tokens("Wind: %s, %d and %1") == tokens("Vento: %s, %d e %1")
    assert tokens("Wind: %s, %d and %1") != tokens("Vento: %s e %1")
