import csv
import threading
from arayzt.analyst import TranslationAnalyst
from arayzt.agents import manager_decision
from arayzt.core import tokens
from arayzt import staged_pipeline
from arayzt.delivery_audit import save_delivery_audit


class Backend:
    name='test-en-pb'
    def translate(self,text):
        return {'Babysitter':'Babá','Take':'Pegar','items':'itens',
                'Open window':'Abrir janela'}.get(text,'Tradução correta')


def row(key='UI_Analyst',en='Babysitter'):
    return {'file':'UI_PTBR.txt','key':key,'en':en,'status':'missing'}


def test_analyst_protects_tokens_markup_newlines_and_whitespace():
    source='Take %1\n<b>items</b>'
    result=TranslationAnalyst(Backend).analyze(row(en=source))
    assert result['status']=='approved'
    assert result['translation']=='Pegar %1\n<b>itens</b>'
    assert tokens(source)==tokens(result['translation'])


def test_preset_repair_never_turns_english_into_an_approval():
    analyst=TranslationAnalyst(Backend)
    fixed=analyst.analyze(row(en='Open window'),'K1 - Abrir janela')
    assert fixed['translation']=='Abrir janela' and fixed['provider']=='preset'
    translated=analyst.analyze(row(en='Open window'),'K1 - Open window')
    assert translated['translation']=='Abrir janela'
    assert translated['provider']=='test-en-pb'


def test_ui_fragment_does_not_gain_an_engine_full_stop():
    class PunctuationBackend:
        name='test'
        def translate(self,text):return 'Dor.'
    analyst=TranslationAnalyst(PunctuationBackend)
    assert analyst.analyze(row(en='Pain'))['translation']=='Dor'
    assert analyst.analyze(row(en='Pain.'))['translation']=='Dor.'


def test_gerente_includes_precise_placeholder_diagnosis():
    decision=manager_decision('rejected',['placeholder_mismatch'],1,
        row=row(en='Take %1'),candidate='Pegar %2')
    assert decision['decision']=='retry'
    assert decision['diagnosis']['marcadores_ausentes']==['%1']
    assert decision['diagnosis']['marcadores_extras']==['%2']
    assert 'UI_Analyst' in decision['context']


def test_failed_ollama_candidate_reaches_analyst_worker_five(monkeypatch):
    calls=[];events=[];results=[]
    def generate(client,records,**kwargs):
        calls.append(records)
        return [{'translation':'Babysitter'}],[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',generate)
    staged_pipeline.orchestrate_pipeline([row()],'http://127.0.0.1:11434','fake',4,
        threading.Event(),results.append,
        lambda slot,row,stage,cycle,detail:events.append((slot,stage)),
        analyst_factory=lambda:TranslationAnalyst(Backend))
    assert len(calls)==2
    assert len(results)==1 and results[0]['status']=='approved'
    assert results[0]['translation']=='Babá'
    assert (5,'analyst') in events
    assert any(h['agent']=='analyst' and h['provider']=='test-en-pb' for h in results[0]['history'])


def test_analyst_cannot_approve_internal_ids_or_create_a_retry_loop(monkeypatch):
    class BadBackend:
        name='bad'
        def translate(self,text):return 'K1 - Babysitter'
    calls=[];results=[]
    def generate(client,records,**kwargs):
        calls.append(records);return [{'translation':'Babysitter'}],[]
    monkeypatch.setattr(staged_pipeline,'translate_rows',generate)
    staged_pipeline.orchestrate_pipeline([row()],'http://127.0.0.1:11434','fake',1,
        threading.Event(),results.append,analyst_factory=lambda:TranslationAnalyst(BadBackend))
    assert len(calls)==2 and len(results)==1
    assert results[0]['status']!='approved'
    assert 'id_prefix_echo' in results[0]['reasons']
    assert sum(h['agent']=='analyst' for h in results[0]['history'])==1


def test_fifth_worker_runs_while_four_ollama_workers_are_busy(monkeypatch):
    barrier=threading.Barrier(5,timeout=3)
    def generate(client,records,**kwargs):
        barrier.wait();return [{'translation':'Tradução correta'}],[]
    class Analyst:
        def analyze(self,row,previous,reasons):
            barrier.wait()
            return {'translation':'Tradução correta','status':'approved','reasons':[],
                    'provider':'test','actions':[]}
    monkeypatch.setattr(staged_pipeline,'translate_rows',generate)
    rows=[row(str(i)) for i in range(4)]+[dict(row('old'),_analyst_resume={'translation':'Bad'})]
    results=[]
    staged_pipeline.orchestrate_pipeline(rows,'http://127.0.0.1:11434','fake',4,
        threading.Event(),results.append,analyst_factory=Analyst)
    assert len(results)==5 and all(r['status']=='approved' for r in results)


def test_custom_preset_cannot_bypass_shared_validation(monkeypatch):
    class UnsafePreset:
        def analyze(self,row,previous,reasons):
            return {'translation':'K1 - Babysitter','status':'approved','reasons':[],
                    'provider':'unsafe','actions':[]}
    monkeypatch.setattr(staged_pipeline,'translate_rows',lambda *a,**k:([{'translation':'Babysitter'}],[]))
    results=[]
    staged_pipeline.orchestrate_pipeline([row()],'http://127.0.0.1:11434','fake',1,
        threading.Event(),results.append,analyst_factory=UnsafePreset)
    assert results[0]['status']!='approved'
    assert 'id_prefix_echo' in results[0]['reasons']


def test_ollama_outage_uses_offline_analyst_and_completes_all_entries(monkeypatch):
    calls=[]
    def unavailable(*args,**kwargs):
        calls.append(1)
        raise ConnectionError('connection refused')
    monkeypatch.setattr(staged_pipeline,'translate_rows',unavailable)
    results=[]
    staged_pipeline.orchestrate_pipeline([row(str(i)) for i in range(5)],
        'http://127.0.0.1:11434','fake',1,threading.Event(),results.append,
        analyst_factory=lambda:TranslationAnalyst(Backend))
    assert len(calls)==1
    assert len(results)==5 and all(r['status']=='approved' for r in results)
    assert all(r['translation']=='Babá' for r in results)


def test_delivery_csv_records_producer_and_actual_export_not_just_proposals(tmp_path):
    output=tmp_path/'export';target=output/'media/lua/shared/Translate/PTBR'
    target.mkdir(parents=True);(target/'UI.json').write_text('{}');(target/'Blocked.json').write_text('{}')
    rows=[dict(row('A'),file='UI.json',ptbr='Antes'),dict(row('B'),file='Blocked.json',ptbr='Antigo')]
    approved=[{'file':'UI.json','key':'A','translation':'Depois','producer':'analyst','provider':'argos-en-pb'},
              {'file':'Blocked.json','key':'B','translation':'Proposta','producer':'translator_ii','provider':'gemma3:4b'}]
    path=save_delivery_audit(tmp_path,{'rows':rows},approved,[],[],[],
        {'output':str(target),'blocked_files':[{'file':'Blocked.json'}]})
    with path.open(encoding='utf-8-sig',newline='') as handle:records=list(csv.DictReader(handle,delimiter=';'))
    assert records[0]['ptbr_antes']=='Antes' and records[0]['ptbr_depois']=='Depois'
    assert records[0]['responsavel']=='analyst' and records[0]['exportado']=='sim'
    assert records[1]['ptbr_depois']=='Antigo' and records[1]['candidata']=='Proposta'
    assert records[1]['exportado']=='nao' and records[1]['motivo']=='file_blocked_or_not_exported'
