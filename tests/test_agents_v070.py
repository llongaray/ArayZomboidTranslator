from arayzt.agents import orchestrate
import threading
from unittest.mock import patch

def test_atomic_results_and_cancel():
    data=[{'file':'UI_PTBR.txt','key':str(i),'en':'Hello','status':'missing'} for i in range(7)]
    seen=[]
    def fake(row,url,model,cancel):
        return {'row':row,'status':'approved','translation':'Olá','reasons':[],'attempts':1}
    with patch('arayzt.agents.translate_atom',side_effect=fake):
        orchestrate(data,'http://127.0.0.1:11434','gemma3:4b',3,threading.Event(),seen.append)
    assert len(seen)==7
    assert {r['row']['key'] for r in seen}=={str(i) for i in range(7)}
