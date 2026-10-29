"""Validacao defensiva de traducoes e arquivos Lua exportados."""
import re
from pathlib import Path
from .core import LUA_ENTRY_RE, tokens
from .quality import review

ASSIGN = re.compile(r"^\s*[A-Za-z_][\w.]*\s*=")
HEADER = re.compile(r"^\s*[A-Za-z_][\w.]*\s*=\s*\{\s*(?:--.*)?$")

def validate_candidate(en, translated, key):
    state, reasons = review(en, translated, key)
    if state == "rejected":
        return state, reasons
    if not isinstance(translated,str):
        return "rejected", ["non_string"]
    s = translated.strip()
    if (s.startswith(("{", "[")) and any(x in s for x in ('"file"', '"key"', '"value"'))) or re.search(r"(?i)\b(?:file|key|value)\s*:\s*\w+_PTBR\.txt",s):
        return "rejected", ["metadata_echo"]
    return state, reasons

def validate_lua(path, changes):
    text = Path(path).read_text(encoding="utf-8-sig")
    matches = list(LUA_ENTRY_RE.finditer(text))
    covered = {text.count("\n",0,m.start())+1 for m in matches}
    problems=[]
    found={}
    for m in matches:
        if m.group("key") in found:problems.append(("duplicate_key",m.group("key")))
        found[m.group("key")]=m.group("value")
    for n,line in enumerate(text.splitlines(),1):
        if ASSIGN.match(line) and not HEADER.match(line) and n not in covered:
            problems.append(("unparsed_assignment",n))
    for k in changes:
        if k not in found:problems.append(("missing_key",k))
    return problems
