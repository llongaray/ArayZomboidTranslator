import json
import threading
from pathlib import Path
from arayzt.analyst import TranslationAnalyst
from arayzt.analyst_rules import cases
from arayzt.validation import validate_candidate
from arayzt import staged_pipeline, jobs
from arayzt.web import app

def test_context_registry_is_fully_validated_without_native_model():
    analyst=TranslationAnalyst(lambda: (_ for _ in ()).throw(AssertionError('Preset must not use inference')))
    for rule in cases().values():
        result=analyst.analyze(dict(rule,en=rule['en']))
        assert result['status']=='approved', (rule,result)
        assert result['translation']==rule['translation']
        assert result['policy_version']==2

def test_context_rules_do_not_approve_unknown_english_or_changed_sources():
    assert validate_candidate('Open the window','Open the window','Unknown')[0]!='approved'
    assert validate_candidate('Normal changed','Normal changed','Sandbox_ZombieRespawn_option2')[0]!='approved'
    assert validate_candidate('Buck','Buck','IGUI_AnimalType_buck')[0]!='approved'
    assert validate_candidate('Hospital','Hospital','Unknown')[0]!='approved'

def test_previously_analyzed_legacy_item_returns_to_analyst(tmp_path,monkeypatch):
    game=tmp_path/'Translate';(game/'EN').mkdir(parents=True);(game/'PTBR').mkdir()
    (game/'EN/UI.json').write_text(json.dumps({'IGUI_UserList_Online':'Online'}))
    work=tmp_path/'work';work.mkdir()
    previous={'file':'UI.json','key':'IGUI_UserList_Online','english':'Online','translation':'Online','reasons':['unchanged_english'], 'history':[{'agent':'analyst','translation':'Online','status':'needs_review'}]}
    (work/'quality-review.json').write_text(json.dumps({'needs_review':[previous]}))
    monkeypatch.setattr(staged_pipeline,'translate_rows',lambda *a,**k: (_ for _ in ()).throw(AssertionError('No Ollama regeneration')))
    result=jobs.Pipeline().run(game,work,translate=True)
    accepted=json.loads((work/'accepted.json').read_text())
    assert result['needs_review']==result['failed']==0
    assert accepted['translations'][0]['translation']=='Online'
    assert accepted['translations'][0]['producer']=='analyst'
    assert json.loads((work/'quality-review.json').read_text())['needs_review']==[]
    again=jobs.Pipeline().run(game,work,translate=True)
    assert again['reused']==1
    assert json.loads((work/'accepted.json').read_text())['translations'][0]['producer']=='analyst'

def test_human_review_mutations_are_retired():
    client=app.test_client()
    for route in ('decision','instruct'):
        assert client.post('/api/review/'+route,json={}).status_code==410
