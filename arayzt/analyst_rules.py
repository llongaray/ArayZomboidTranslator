"""Context-specific analyst decisions, bound to the exact source and key."""
import json
from functools import lru_cache
from pathlib import Path
POLICY_VERSION = 2
@lru_cache(maxsize=1)
def cases():
    data=json.loads((Path(__file__).parent/'data'/'analyst_cases_ptbr.json').read_text(encoding='utf-8'))
    return {(r['key'],r['en']):r for r in data['entries']}
def resolution(key, source):
    return cases().get((key,source))
def valid_literal(key, source):
    rule=resolution(key,source)
    return bool(rule and rule['translation']==source)
