import csv
import io
import json
from arayzt.review_csv import report_csv, save_report, report_rows
from arayzt.web import app

def test_review_csv_has_source_translation_reasons_and_cycles(tmp_path):
    (tmp_path/'quality-review.json').write_text(json.dumps({'needs_review':[
        {'file':'IG_UI_PTBR.txt','key':'IGUI_abc','english':'Ready; Go\nNow',
         'translation':'Pronto; Vamos\nAgora','quality':'needs_review','reasons':['unusual_length']},
        {'file':'Tooltip_PTBR.txt','key':'Tooltip_abc','english':'Wait','translation':'',
         'quality':'needs_review','reasons':['placeholder_mismatch']}
    ]}),encoding='utf-8')
    (tmp_path/'agent-history.json').write_text(json.dumps({'items':[
        {'file':'IG_UI_PTBR.txt','key':'IGUI_abc','history':[
            {'agent':'translator','cycle':1},{'agent':'supervisor','cycle':1,'reasons':['unchanged_english']},
            {'agent':'translator','cycle':2},{'agent':'supervisor','cycle':2,'reasons':['unusual_length']}
        ]}
    ]}),encoding='utf-8')
    output=report_csv(tmp_path)
    assert output.startswith('\ufeff')
    rows=list(csv.DictReader(io.StringIO(output.lstrip('\ufeff')),delimiter=';'))
    assert len(rows)==2
    assert rows[0]['original_en']=='Ready; Go\nNow'
    assert rows[0]['traducao_ptbr']=='Pronto; Vamos\nAgora'
    assert rows[0]['motivo_rh']=='unusual_length'
    assert rows[0]['ciclos']=='2'
    assert 'unchanged_english' in rows[0]['historico_motivos']
    assert save_report(tmp_path).read_bytes().startswith(b'\xef\xbb\xbf')
    res=app.test_client().get('/api/review/report.csv',query_string={'work':str(tmp_path)})
    assert res.status_code==410
    assert res.json['replacement']=='/api/analyst/report'
