"""Strict Lua syntax gate and conservative, locally verifiable repairs.

Never execute Lua. A proposed repair is delivered only when the entire file
parses under luaparser; otherwise the file is blocked with diagnostics.
"""
from __future__ import annotations
import re
from pathlib import Path
from luaparser import ast

ASSIGN = re.compile(r'^(\s*[A-Za-z_][\w.]*\s*=\s*)"((?:\\.|[^"\\])*)"(\s*,?\s*(?:--.*)?)$')
SIMPLE_START = re.compile(r'^\s*[A-Za-z_][\w.]*\s*=\s*"')

def syntax_error(text: str) -> str | None:
    try:
        ast.parse(text)
        return None
    except Exception as exc:
        return str(exc)[:500]

def safe_repair(text: str) -> tuple[str,list[str]]:
    """Only add a missing separator after an unambiguous complete string entry."""
    lines=text.splitlines(keepends=True)
    fixes=[]
    for i in range(len(lines)-1):
        raw=lines[i]
        body=raw.rstrip('\r\n')
        match=ASSIGN.fullmatch(body)
        if not match or ',' in match.group(3).split('--',1)[0]:
            continue
        nxt=lines[i+1]
        if SIMPLE_START.match(nxt):
            before=lines[i]
            line_end='\r\n' if before.endswith('\r\n') else ('\n' if before.endswith('\n') else '')
            lines[i]=body.rstrip()+','+line_end
            fixes.append(f'added_separator_line_{i+1}')
    return ''.join(lines),fixes

def certify(path: Path) -> dict:
    text=Path(path).read_text(encoding='utf-8-sig')
    err=syntax_error(text)
    if err is None:return {'valid':True,'repaired':False,'fixes':[]}
    repaired,fixes=safe_repair(text)
    if fixes and syntax_error(repaired) is None:
        Path(path).write_text(repaired,encoding='utf-8')
        return {'valid':True,'repaired':True,'fixes':fixes}
    return {'valid':False,'repaired':False,'fixes':[],'error':err}
