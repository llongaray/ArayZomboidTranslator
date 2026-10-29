from pathlib import Path
from arayzt.lua_syntax import certify, syntax_error, safe_repair
from arayzt.core import write_lua_overlay, read_lua, select_rows

def test_escaped_internal_quotes_and_comma(tmp_path):
    path=tmp_path/'UI_PTBR.txt'
    path.write_text('UI_PTBR = {\n A = "Deletar "%1"?"\n B = "Outro",\n}\n',encoding='utf8')
    assert syntax_error(path.read_text(encoding='utf8'))
    result=certify(path)
    assert result['valid'] and result['repaired']
    assert read_lua(path)['A']=='Deletar "%1"?'

def test_does_not_claim_unsafe_repair(tmp_path):
    path=tmp_path/'bad.txt'
    path.write_text('UI_PTBR = { A = function(\n',encoding='utf8')
    assert certify(path)['valid'] is False

def test_overlay_does_not_touch_original(tmp_path):
    src=tmp_path/'src.txt'
    target=tmp_path/'out.txt'
    en=tmp_path/'en.txt'
    original='UI_PTBR = {\n A = "Deletar "%1"?",\n}\n'
    src.write_text(original,encoding='utf8')
    en.write_text('UI_EN = { A = "Delete", }\n',encoding='utf8')
    write_lua_overlay(target,src,en,{'A':'Excluir "%1"?'})
    assert src.read_text(encoding='utf8')==original
    assert read_lua(target)['A']=='Excluir "%1"?'
    assert syntax_error(target.read_text(encoding='utf8')) is None

def test_skips_blank_source():
    report={'rows':[{'file':'UI_PTBR.txt','status':'missing','en':'','key':'A'},{'file':'UI_PTBR.txt','status':'missing','en':'Hello','key':'B'}]}
    assert [r['key'] for r in select_rows(report,'all','UI')]==['B']
