import io
import json
import threading
from collections import Counter

from arayzt import jobs, staged_pipeline
from arayzt.ollama import OllamaClient, translate_rows
from arayzt.validation import validate_candidate


def row(key='UI_Fast_A', en='Open the window', file='UI_PTBR.txt'):
    return {'file':file,'key':key,'en':en,'status':'missing'}


def test_reviewed_invariants_are_key_and_source_bound(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Known exact invariant must not call Ollama')
    monkeypatch.setattr(staged_pipeline,'translate_rows',forbidden)
    result=[]
    staged_pipeline.orchestrate_pipeline([row('IGUI_hospitalroomKey','Hospital')],
        'http://127.0.0.1:11434','fake',1,threading.Event(),result.append)
    assert result[0]['status']=='approved'
    assert validate_candidate('Hospital','Hospital','UI_Unknown')[0]=='needs_review'
    assert validate_candidate('Hospital wing','Hospital wing','IGUI_hospitalroomKey')[0]=='needs_review'


def test_repeated_candidate_stops_after_one_correction(monkeypatch):
    calls=[]
    def generate(client, records, **kw):
        calls.append(records)
        return [{'translation':'Open the window'}],[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',generate)
    result=[]
    staged_pipeline.orchestrate_pipeline([row()],'http://127.0.0.1:11434','fake',1,
        threading.Event(),result.append)
    assert len(calls)==2
    assert result[0]['status']=='rejected'
    assert 'no_progress' in result[0]['reasons']
    assert calls[1][0]['manager_feedback']


def test_small_batches_and_atomic_corrections(monkeypatch):
    calls=[]
    counts=Counter()
    def generate(client, records, **kw):
        calls.append([dict(r) for r in records])
        output=[]
        for r in records:
            counts[r['key']]+=1
            value=r['en'] if r['key']=='UI_Fast_B' and counts[r['key']]==1 else 'Texto traduzido'
            output.append({'file':r['file'],'key':r['key'],'translation':value})
        return output,[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',generate)
    result=[]
    rows=[row('UI_Fast_'+c) for c in 'ABCD']
    staged_pipeline.orchestrate_pipeline(rows,'http://127.0.0.1:11434','fake',1,
        threading.Event(),result.append,batch_size=4)
    assert [len(batch) for batch in calls]==[4,1]
    assert calls[1][0]['key']=='UI_Fast_B'
    assert counts=={'UI_Fast_A':1,'UI_Fast_B':2,'UI_Fast_C':1,'UI_Fast_D':1}
    assert all(r['status']=='approved' for r in result)


def test_batches_do_not_mix_files_or_long_sources(monkeypatch):
    calls=[]
    def generate(client, records, **kw):
        calls.append(records)
        return [{'file':r['file'],'key':r['key'],'translation':'Tradução correta'} for r in records],[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',generate)
    rows=[row('UI_'+str(i)) for i in range(6)]+[row('Long','Source '*50),row('Other',file='Other_PTBR.txt')]
    result=[]
    staged_pipeline.orchestrate_pipeline(rows,'http://127.0.0.1:11434','fake',2,
        threading.Event(),result.append,batch_size=4)
    assert len(result)==len(rows)
    assert len({r['row']['key'] for r in result})==len(rows)
    for batch in calls:
        assert len(batch)<=4
        assert len({r['file'] for r in batch})==1
        if any(len(r['en'])>160 for r in batch):assert len(batch)==1
        if len(batch)>1:assert sum(len(r['en']) for r in batch)<=600


def test_one_bad_json_item_does_not_discard_valid_batch_items(monkeypatch):
    body=json.dumps({'response':json.dumps({'translations':{'k0':'Abrir a janela','k1':'Pegar'}})}).encode()
    monkeypatch.setattr('arayzt.ollama.urlopen',lambda *args,**kwargs:io.BytesIO(body))
    output,errors=translate_rows(OllamaClient(),[row(),row('UI_B','Take %1')],batch_size=2,retries=0)
    assert len(output)==1 and output[0]['key']=='UI_Fast_A'
    assert len(errors)==1 and errors[0]['key']=='UI_B'
    assert 'Marcador' in errors[0]['error']


def test_internal_id_prefixes_are_never_approved_or_cached(monkeypatch):
    for candidate in ['K1 - Babysitter','k3: Butcher','K2 — Nome']:
        assert validate_candidate('Babysitter',candidate,'IGUI_Babysitter') == ('rejected',['id_prefix_echo'])
    body=json.dumps({'response':json.dumps({'translations':{'k0':'Abrir a janela','k1':'K1 - Butcher'}})}).encode()
    monkeypatch.setattr('arayzt.ollama.urlopen',lambda *args,**kwargs:io.BytesIO(body))
    output,errors=translate_rows(OllamaClient(),[row(),row('UI_B','Butcher')],batch_size=2,retries=0)
    assert len(output)==1 and output[0]['key']=='UI_Fast_A'
    assert errors[0]['error']=='id_prefix_echo'
    assert validate_candidate('K1 - Setor','K1 - Setor','UI_Legitimate')[0]!='rejected'


def make_game(path,en='Open the window'):
    game=path/'Translate'
    (game/'EN').mkdir(parents=True)
    (game/'PTBR').mkdir()
    (game/'EN/UI.json').write_text(json.dumps({'UI_Fast_A':en}),encoding='utf-8')
    return game


def test_human_review_is_preserved_on_resume_and_invalidated_by_source_change(tmp_path,monkeypatch):
    game=make_game(tmp_path)
    work=tmp_path/'work'
    calls=[]
    def generate(client,records,**kwargs):
        calls.extend(records)
        return [{'translation':records[0]['en']}],[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',generate)
    result=jobs.Pipeline().run(game,work,translate=True,batch=1)
    assert result['needs_review']==0 and result['failed']==1 and len(calls)==2
    saved=json.loads((work/'analysis-report.json').read_text(encoding='utf-8'))
    assert len(saved['items'])==1
    again=jobs.Pipeline().run(game,work,translate=True,batch=1)
    assert again['preserved_review']==0 and len(calls)==2
    assert again['needs_review']==0 and again['failed']==1
    history=json.loads((work/'agent-history.json').read_text(encoding='utf-8'))
    assert history['items'][0]['history']
    (game/'EN/UI.json').write_text(json.dumps({'UI_Fast_A':'Close the door'}),encoding='utf-8')
    changed=jobs.Pipeline().run(game,work,translate=True,batch=1)
    assert changed['preserved_review']==0 and len(calls)==4


def test_existing_review_report_is_imported_without_approving_english(tmp_path,monkeypatch):
    game=make_game(tmp_path)
    work=tmp_path/'work'
    work.mkdir()
    previous={'file':'UI.json','key':'UI_Fast_A','english':'Open the window',
              'translation':'Open the window','reasons':['unchanged_english']}
    (work/'quality-review.json').write_text(json.dumps({'needs_review':[previous]}),encoding='utf-8')
    monkeypatch.setattr(staged_pipeline,'translate_rows',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No regeneration')))
    result=jobs.Pipeline().run(game,work,translate=True,batch=4)
    # Old RH is migrated to the analyst without regenerating it with Ollama.
    # The deterministic unavailable backend leaves a justified review pending.
    assert result['needs_review']==0 and result['failed']==1 and result['preserved_review']==0
    assert result['translated']==0


def test_approved_checkpoint_wins_over_an_older_review_report(tmp_path,monkeypatch):
    from arayzt.core import audit
    game=make_game(tmp_path)
    work=tmp_path/'work';work.mkdir()
    record=audit(game)['rows'][0]
    previous={'file':record['file'],'key':record['key'],'english':record['en'],
              'translation':record['en'],'reasons':['unchanged_english']}
    (work/'quality-review.json').write_text(json.dumps({'needs_review':[previous]}),encoding='utf-8')
    entry={'translation':'Abrir a janela','quality':'approved','producer':'analyst','provider':'argos-en-pb:1.9'}
    (work/'checkpoint-v040.json').write_text(json.dumps({jobs.fingerprint(record):entry}),encoding='utf-8')
    monkeypatch.setattr(staged_pipeline,'translate_rows',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Do not regenerate')))
    result=jobs.Pipeline().run(game,work,translate=True)
    assert result['needs_review']==0 and result['reused']==1 and result['translated']==1
