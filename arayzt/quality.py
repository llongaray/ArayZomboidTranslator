"""Conservative translation quality checks (heuristics, not language certification)."""
from __future__ import annotations
import re
from .core import tokens

GLOSSARY = {
    'Sleep on Ground with Pillow': 'Dormir no chão com travesseiro',
    'Tie Escape Rope': 'Amarrar corda de fuga',
    'Nail Escape Rope': 'Pregar corda de fuga',
    'Tie Escape Rope (Fabric)': 'Amarrar corda de fuga (tecido)',
    'Nail Escape Rope (Fabric)': 'Pregar corda de fuga (tecido)',
}
EN_WORDS = {'the','with','from','your','sleep','ground','pillow','and','open','drink','remove','add','escape','rope','nail','tie','weapon','window','door','player'}
PT_WORDS = {'com','sem','para','uma','um','do','da','de','no','na','abrir','dormir','chão','travesseiro','corda','fuga','pregar','amarrar','remover','janela','porta'}

def review(en: str, translated: str, key: str = '') -> tuple[str, list[str]]:
    """Return approved / needs_review / rejected and rule codes."""
    if not isinstance(translated,str) or not translated.strip():
        return 'rejected',['empty_translation']
    if tokens(en) != tokens(translated):
        return 'rejected',['placeholder_mismatch']
    issues=[]
    if en.strip().casefold()==translated.strip().casefold():
        issues.append('unchanged_english')
    original_words=set(re.findall(r"[a-zA-Z]+",en.casefold()))
    new_words=set(re.findall(r"[a-zA-Z]+",translated.casefold()))
    if len(original_words & EN_WORDS)>=2 and len(new_words & EN_WORDS)>=2 and not len(new_words & PT_WORDS):
        issues.append('suspected_english')
    if len(translated)>max(30,len(en)*4):issues.append('unusual_length')
    if en in GLOSSARY and translated.casefold()!=GLOSSARY[en].casefold():issues.append('glossary_mismatch')
    return ('needs_review' if issues else 'approved'),issues
