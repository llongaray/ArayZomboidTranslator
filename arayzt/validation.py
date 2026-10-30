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
    from .translation_text import parse, serialize
    from .lua_syntax import syntax_error
    try:
        doc=parse(Path(path).read_text(encoding='utf-8-sig'))
    except ValueError as exc:return [('invalid_document',str(exc))]
    problems=[(w['kind'],w.get('key',w.get('line',''))) for w in doc.warnings]
    problems.extend((w['kind'],w.get('line','')) for w in doc.unsupported)
    if not doc.unsupported:
        error=syntax_error(serialize(doc,doc.entries,lua=True))
        if error:problems.append(('invalid_lua_representation',error))
    for key in changes:
        if key not in doc.entries:problems.append(('missing_key',key))
    return problems


def validate_lua_comparative(output_path, source_path, changes):
    """Report pre-existing parser warnings separately; block only introduced warnings.

    The parser is line-based, so this is a comparison, not a complete Lua syntax proof.
    """
    from collections import Counter
    before=validate_lua(source_path,{}) if Path(source_path).is_file() else []
    after=validate_lua(output_path,changes)
    def normalized(issue):
        if isinstance(issue,(tuple,list)):
            return (issue[0],issue[1]) if issue[0]=='missing_key' else (issue[0],)
        return str(issue)
    delta=Counter(normalized(x) for x in after)-Counter(normalized(x) for x in before)
    return {'preexisting':before,'introduced':list(delta.elements())}
