import json
import pytest
from arayzt.core import audit, read_lua
from arayzt.jobs import fingerprint
from arayzt.delivery import reexport
from arayzt.linguistic_audit import reviewed_translation

def create(tmp_path):
    game=tmp_path/'Translate';(game/'EN').mkdir(parents=True);(game/'PTBR').mkdir()
    (game/'EN/BodyParts_EN.txt').write_text('BodyParts_EN = {\n BODYPART_LEFT_LOWER_LEG = "Left Lower Leg",\n}\n')
    report=audit(game);row=report['rows'][0];work=tmp_path/'work';work.mkdir()
    approved={'file':row['file'],'key':row['key'],'translation':'Meia inferior esquerda','producer':'translator'}
    for name,value in [('audit.json',report),('accepted.json',{'translations':[approved],'needs_review':[],'failed':[]}),('checkpoint-v040.json',{fingerprint(row):{'translation':approved['translation'],'quality':'approved'}})]:
        (work/name).write_text(json.dumps(value))
    return work,game

def test_reexport_reuses_checkpoint_corrects_only_reviewed_anatomy_and_is_idempotent(tmp_path,monkeypatch):
    from arayzt.ollama import OllamaClient
    monkeypatch.setattr(OllamaClient,'__init__',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No model allowed')))
    work,game=create(tmp_path)
    result=reexport(work)
    assert result['reused']==result['exported_entries']==1
    assert result['approved_unexported']==0 and result['linguistic_corrections']==1
    assert read_lua(work/'export/media/lua/shared/Translate/PTBR/BodyParts_PTBR.txt')['BODYPART_LEFT_LOWER_LEG']=='Perna esquerda'
    accepted=json.loads((work/'accepted.json').read_text())
    assert len(accepted['translations'])==1 and accepted['translations'][0]['producer']=='analyst'
    saved=next((work/'export-snapshots').glob('*/checkpoint-v040.json'))
    assert 'Meia inferior esquerda' in saved.read_text()
    again=reexport(work)
    assert again['linguistic_corrections']==0 and again['reused']==1
    assert json.loads((work/'linguistic-audit.json').read_text())['previous_bodyparts_review'][0]['before']=='Meia inferior esquerda'

def test_changed_source_aborts_before_checkpoint_mutation(tmp_path):
    work,game=create(tmp_path);before=(work/'checkpoint-v040.json').read_bytes()
    (game/'EN/BodyParts_EN.txt').write_text('BodyParts_EN = {\n BODYPART_LEFT_LOWER_LEG = "Changed",\n}\n')
    with pytest.raises(ValueError,match='EN changed'):reexport(work)
    assert (work/'checkpoint-v040.json').read_bytes()==before

def test_anatomy_correction_is_bound_to_exact_source_and_file():
    base={'file':'BodyParts_PTBR.txt','key':'BODYPART_LEFT_LOWER_LEG','en':'Left Lower Leg'}
    assert reviewed_translation(base)=='Perna esquerda'
    assert reviewed_translation({**base,'en':'Changed'}) is None
    assert reviewed_translation({**base,'file':'Other.txt'}) is None


def test_contextual_fixes_preserve_markers_and_source_binding():
    from arayzt.linguistic_audit import CONTEXTS
    from arayzt.core import tokens
    from arayzt.validation import validate_candidate
    for (file,key,en),translation in CONTEXTS.items():
        assert tokens(en)==tokens(translation)
        assert validate_candidate(en,translation,key)[0]=='approved'
        assert reviewed_translation({'file':file,'key':key,'en':en})==translation
        assert reviewed_translation({'file':file,'key':key,'en':en+' changed'}) is None
