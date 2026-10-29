from arayzt.agents import translate_atom
from arayzt.context_glossary import CURATED, INVARIANT
import threading

def test_curated_translation_without_llm():
    row={'file':'ContextMenu_PTBR.txt','key':'ContextMenu_Barricades','en':'Barricades','status':'missing'}
    result=translate_atom(row,'http://127.0.0.1:11434','gemma3:4b',threading.Event())
    assert result['status']=='approved'
    assert result['translation']=='Barricadas'
    assert result['attempts']==0

def test_invariant_key_without_llm():
    row={'file':'UI_PTBR.txt','key':'UI_servers_default_name','en':'John Smith','status':'missing'}
    result=translate_atom(row,'http://127.0.0.1:11434','gemma3:4b',threading.Event())
    assert result['translation']=='John Smith'
    assert result['status']=='approved'

def test_glossary_scope():
    assert CURATED['Moodles_Thirst_lvl1']=='Pouca sede'
    assert 'UI_ClothingType_SCBA' in INVARIANT
