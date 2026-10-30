import csv
import json
import pytest
from pathlib import Path
from arayzt.core import audit, export_overlay, read_lua, tokens
from arayzt.translation_text import parse, serialize
from arayzt.lua_syntax import syntax_error
from arayzt.delivery_audit import save_delivery_audit
from arayzt.web import completion_status


def setup_game(tmp_path, en, pt=None):
    root=tmp_path/'Translate';(root/'EN').mkdir(parents=True);(root/'PTBR').mkdir()
    (root/'EN/UI_EN.txt').write_text(en,encoding='utf-8')
    if pt is not None:(root/'PTBR/UI_PTBR.txt').write_text(pt,encoding='utf-8')
    return root


@pytest.mark.parametrize('key',['ItemName_Base.223Box','50s_Barstool','Aaaaah!_Painting',"Bob's Chair",'UI_Key-with/slash','end','Árvore'])
def test_special_literal_keys_match_game_and_have_strict_lua_representation(tmp_path,key):
    game=setup_game(tmp_path,f'UI_EN = {{\n {key} = "Source",\n}}\n')
    report=audit(game)
    result=export_overlay(report,[{'file':'UI_PTBR.txt','key':key,'translation':'Tradução'}],tmp_path/'out')
    assert result['delivery_status']=='success'
    text=(Path(result['output'])/'UI_PTBR.txt').read_text(encoding='utf-8')
    line=text.splitlines()[1]
    # PZ Translator.java uses the literal left-hand side, NOT Lua evaluation.
    assert line.split('=',1)[0].strip()==key
    assert read_lua(Path(result['output'])/'UI_PTBR.txt')[key]=='Tradução'
    lua=(tmp_path/'lua-certified/PTBR/UI_PTBR.lua').read_text(encoding='utf-8')
    assert syntax_error(lua) is None
    assert parse(lua,strict=True).entries[key]=='Tradução'


def test_comments_delimiters_concatenation_and_markers_are_preserved():
    text='''UI_PTBR = {
 -- comentário com } e "aspas" e ]]
 /* Inativo = "não ativar", */
 A = "Texto -- /* literal */ %1 " ..
     "<LINE> {player}";
 B = "Aspas "internas"", -- último comentário
}
'''
    doc=parse(text,strict=True)
    assert 'Inativo' not in doc.entries
    assert doc.entries['A']=='Texto -- /* literal */ %1 <LINE> {player}'
    for lua in (False,True):
        out=serialize(doc,doc.entries,lua=lua)
        assert parse(out,strict=True).entries==doc.entries
        assert 'último comentário' in out
        assert tokens(parse(out).entries['A'])==tokens(doc.entries['A'])
        if lua:assert syntax_error(out) is None


def test_native_quotes_and_backslashes_have_exact_game_reader_values():
    doc=parse('UI_PTBR = {\n A = "Original",\n}\n')
    value='Pressione "%1", caminho C:\\mapas\\ -- fim'
    text=serialize(doc,{'A':value})
    line=text.splitlines()[1]
    # Java extracts everything between first and last double quote, no unescaping.
    assert line[line.index('"')+1:line.rindex('"')]==value
    assert parse(text,strict=True).entries['A']==value
    assert syntax_error(serialize(doc,{'A':value},lua=True)) is None


def test_recovers_bad_existing_file_without_losing_translations(tmp_path):
    original='UI_PTBR = {\n Old = "Leia "Geradores""\n Another = "Mantenha %1";\n}\n'
    game=setup_game(tmp_path,'UI_EN = {\n New = "Hello",\n}\n',original)
    report=audit(game)
    result=export_overlay(report,[{'file':'UI_PTBR.txt','key':'New','translation':'Olá'}],tmp_path/'out')
    assert result['delivery_status']=='success'
    assert read_lua(Path(result['output'])/'UI_PTBR.txt')=={'Old':'Leia "Geradores"','Another':'Mantenha %1','New':'Olá'}
    assert (game/'PTBR/UI_PTBR.txt').read_text(encoding='utf-8')==original


def test_unsupported_existing_code_blocks_but_never_deletes_valid_previous_output(tmp_path):
    game=setup_game(tmp_path,'UI_EN = {\n New = "Hello",\n}\n','UI_PTBR = {\n Old = function() return "No" end,\n}\n')
    target=tmp_path/'out/media/lua/shared/Translate/PTBR/UI_PTBR.txt';target.parent.mkdir(parents=True)
    prior=b'UI_PTBR = {\n Existing = "Seguro",\n}\n';target.write_bytes(prior)
    result=export_overlay(audit(game),[{'file':'UI_PTBR.txt','key':'New','translation':'Olá'}],tmp_path/'out')
    assert result['delivery_status']=='partial' and result['approved_unexported']==1
    assert target.read_bytes()==prior
    assert result['blocked_files'][0]['previous_output_preserved']


def test_header_and_stray_delimiter_recovery():
    doc=parse('RecipeGroupsEN {\n A = "Primeiro " ..\n "Segundo" ..,\n B = "Fim",}\n',strict=True)
    assert doc.entries=={'A':'Primeiro Segundo','B':'Fim'}
    assert syntax_error(serialize(doc,doc.entries,lua=True)) is None


def test_placeholder_corruption_never_replaces_previous_file(tmp_path):
    game=setup_game(tmp_path,'UI_EN = {\n A = "Hello %1 <LINE> {name}",\n}\n')
    target=tmp_path/'out/media/lua/shared/Translate/PTBR/UI_PTBR.txt';target.parent.mkdir(parents=True)
    target.write_bytes(b'unchanged')
    with pytest.raises(ValueError):
        export_overlay(audit(game),[{'file':'UI_PTBR.txt','key':'A','translation':'Olá %2 <LINE> {name}'}],tmp_path/'out')
    assert target.read_bytes()==b'unchanged'


def test_partial_delivery_is_not_done_even_without_block_list():
    assert completion_status({'delivery_status':'partial','files':10})=='partial'
    assert completion_status({'delivery_status':'success','approved_unexported':1})=='partial'
    assert completion_status({'delivery_status':'success','approved_unexported':0})=='done'


def test_csv_does_not_count_stale_file_as_delivered(tmp_path):
    out=tmp_path/'out';out.mkdir();(out/'UI.json').write_text('{"A":"Antigo"}')
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'entries':[{'file':'UI.json','key':'A','translation':'Novo'}]}))
    path=save_delivery_audit(tmp_path,{'rows':[{'file':'UI.json','key':'A','en':'New','ptbr':'Antes'}]},
        [{'file':'UI.json','key':'A','translation':'Novo'}],[],[],[],{'output':str(out),'manifest':str(manifest)})
    with path.open(encoding='utf-8-sig') as f:record=next(csv.DictReader(f,delimiter=';'))
    assert record['status']=='approved_not_exported' and record['ptbr_depois']=='Antes'


def test_nonliteral_expression_never_becomes_a_translation():
    with pytest.raises(ValueError,match='nonliteral'):
        parse('UI_PTBR = {\n A = "x" .. os.getenv("SECRET") .. "y",\n}\n',strict=True)
