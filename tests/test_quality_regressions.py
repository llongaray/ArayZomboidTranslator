from arayzt.quality import review
from arayzt.ollama import OllamaClient
from unittest.mock import patch
import json

def test_filename_echo_rejected():
    for value in ('ContextMenu_PTBR.txt','file: UI_PTBR.txt','UI_PTBR.txt','ContextMenu_ReLook_at_pictures','k0'):
        state,reasons=review('Look at pictures',value,'ContextMenu_ReLook_at_pictures')
        assert state=='rejected' and 'structural_echo' in reasons

def test_real_translation_approved():
    assert review('Sleep on Ground with Pillow','Dormir no chão com travesseiro')[0]=='approved'

def test_malformed_single_key_response_recovered():
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
    x=Response()
    x.read=lambda:json.dumps({"response":json.dumps({"translations":{"wrong_id":"Dormir no chão com travesseiro"}})}).encode()
    with patch('arayzt.ollama.urlopen',return_value=x):
        items=OllamaClient().generate([{'key_id':'k0','key':'ContextMenu_SleepOnGroundPillow','file':'ContextMenu_PTBR.txt','en':'Sleep on Ground with Pillow','status':'missing'}])
    assert items[0]['translation']=='Dormir no chão com travesseiro'
