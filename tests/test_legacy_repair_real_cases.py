from arayzt.legacy_repair import repair_legacy
from arayzt.lua_syntax import syntax_error

def test_spaced_keys_and_quoted_generator_title():
    source='ContextMenu_PTBR = {\n    ContextMenu_EvolvedRecipe_Stir fry = "Stir Fry",\n    ContextMenu_GeneratorPlugTT = "Leia "Como Usar Geradores" primeiro.",\n}\n'
    output,fixes=repair_legacy(source)
    assert '["ContextMenu_EvolvedRecipe_Stir fry"]' in output
    assert 'Leia \\"Como Usar Geradores\\" primeiro.' in output
    assert fixes and syntax_error(output) is None

def test_missing_commas_and_invalid_percent_escape():
    source='UI_PTBR = {\n    UI_clock_small = "Pequeno"\n    UI_clock_large = "Grande"\n    UI_pressKey = "Pressione \\\\%1",\n}\n'
    output,fixes=repair_legacy(source)
    assert 'Pequeno",' in output
    assert syntax_error(output) is None

def test_orphaned_strings_under_commented_assignment():
    source='UI_PTBR = {\n -- UI_News = "ABC" ..\n "Continuação de ABC" ..\n "Fim do comentário",\n UI_Active = "Ativo",\n}\n'
    output,fixes=repair_legacy(source)
    assert '-- "Continuação de ABC"' in output
    assert syntax_error(output) is None

def test_unknown_backslash_escape_is_preserved_as_literal():
    source='UI_PTBR = {\n    UI_Key = "A tecla \\m e \\%1",\n}\n'
    output,fixes=repair_legacy(source)
    assert fixes
    assert syntax_error(output) is None
