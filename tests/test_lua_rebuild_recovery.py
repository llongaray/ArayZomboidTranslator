from arayzt.lua_rebuild import recover
from arayzt.lua_syntax import syntax_error

def test_recover_bad_quotes_and_missing_separator():
    text='UI_PTBR = {\n A = "Deletar "%1"?"\n B = "Texto",\n}\n'
    repaired,info=recover(text,{'B':'Revisado'})
    assert info['valid'],info
    assert syntax_error(repaired) is None
    assert 'Deletar \\"%1\\"?' in repaired
    assert 'B = "Revisado"' in repaired

def test_fail_closed_on_unsupported_lua():
    text='UI_PTBR = {\n A = function() return "x" end,\n}\n'
    rebuilt,info=recover(text,{})
    assert not info['valid']
    assert not rebuilt

def test_preserve_untouched_entries():
    text='ContextMenu_PTBR = {\n A = "Olá",\n B = "Existente",\n}\n'
    rebuilt,info=recover(text,{'A':'Novo'})
    assert info['valid']
    assert 'B = "Existente"' in rebuilt
