import json
from arayzt.review_instructions import instruct
from arayzt.manual_review import read_decisions

def test_instruction_applies_only_to_requested_file_and_validates(tmp_path,monkeypatch):
    audit={'rows':[
        {'file':'UI_PTBR.txt','key':'UI_Bottle','en':'Bottle 90%','ptbr':None,'status':'missing'},
        {'file':'Tooltip_PTBR.txt','key':'Tooltip_Bottle','en':'Bottle','ptbr':None,'status':'missing'}]}
    (tmp_path/'audit.json').write_text(json.dumps(audit),encoding='utf8')
    data={'needs_review':[
        {'file':'UI_PTBR.txt','key':'UI_Bottle','english':'Bottle 90%','translation':'Garrafa 90% high'},
        {'file':'Tooltip_PTBR.txt','key':'Tooltip_Bottle','english':'Bottle','translation':'Bottle'}]}
    (tmp_path/'quality-review.json').write_text(json.dumps(data),encoding='utf8')
    calls=[]
    def fake_translate(client,rows,batch_size=1,retries=0):
        calls.extend(rows)
        return [{'translation':'Garrafa 90%'}],[]
    monkeypatch.setattr('arayzt.review_instructions.translate_rows',fake_translate)
    result=instruct(tmp_path,'UI_PTBR.txt',"deixar apenas garrafa 90%",limit=20)
    assert result['approved']==1 and result['processed']==1
    assert 'garrafa 90%' in calls[0]['manager_feedback']
    decisions=read_decisions(tmp_path)
    assert len(decisions)==1
    assert next(iter(decisions.values()))['translation']=='Garrafa 90%'

def test_reject_empty_instruction(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        instruct(tmp_path,'UI_PTBR.txt','')
