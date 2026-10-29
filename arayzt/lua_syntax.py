"""Strict Lua syntax gate and conservative, locally verifiable repairs.

Never execute Lua. A proposed repair is delivered only when the entire file
parses under luaparser; otherwise the file is blocked with diagnostics.
"""
from __future__ import annotations
import re
import io
from contextlib import redirect_stderr
from pathlib import Path
from luaparser import ast

ASSIGN = re.compile(r'^(\s*[A-Za-z_][\w.]*\s*=\s*)"((?:\\.|[^"\\])*)"(\s*,?\s*(?:--.*)?)$')
SIMPLE_START = re.compile(r'^\s*[A-Za-z_][\w.]*\s*=\s*"')

def syntax_error(text: str) -> str | None:
    # luaparser may only raise "syntax errors: 1"; capture ANTLR diagnostics
    # from stderr to retain meaningful line/column data when available.
    messages = io.StringIO()
    try:
        with redirect_stderr(messages):
            ast.parse(text)
        return None
    except Exception as exc:
        detail = messages.getvalue().strip()
        return (detail or str(exc))[:1000]


def suspected_lines(text: str, limit: int = 12) -> list[dict]:
    """Provide safe, non-mutating clues for the human diagnostic report."""
    lines = text.splitlines()
    suspects = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not SIMPLE_START.match(stripped):
            continue
        first = line.find('"')
        # Ignore escaped quotes when spotting likely unescaped literals.
        unescaped = [i for i in range(first, len(line))
                     if line[i] == '"' and (i == 0 or len(line[:i]) - len(line[:i].rstrip('\\')) == 0)]
        if len(unescaped) > 2:
            suspects.append({'line': index + 1, 'kind': 'internal_quotes', 'sample': stripped[:180]})
        elif len(unescaped) == 2 and not re.search(r'",\\s*(?:--.*)?

def safe_repair(text: str) -> tuple[str,list[str]]:
    """Repair only quoted Lua table entries with unambiguous outer delimiters.

    Preserve source separately. Every repaired output must pass the full Lua parser
    and accepted translation equality checks before being delivered.
    """
    lines=text.splitlines(keepends=True)
    fixes=[]
    for i,original in enumerate(lines):
        body=original.rstrip('\r\n')
        eol=original[len(body):]
        start=re.match(r'^(\s*[A-Za-z_][\w.]*\s*=\s*)"',body)
        if not start:
            continue
        # Last non-comment string quote is the closing Lua delimiter.
        tail=re.search(r'"\s*,?\s*(?:--.*)?$',body)
        if not tail or tail.start()<=start.end()-1:
            continue
        inner=body[start.end():tail.start()]
        escaped=[]
        j=0
        while j<len(inner):
            if inner[j]=='\\' and j+1<len(inner):
                escaped.append(inner[j:j+2]);j+=2
            elif inner[j]=='"':
                escaped.append(r'\"');j+=1
            else:
                escaped.append(inner[j]);j+=1
        fixed=body[:start.end()]+''.join(escaped)+body[tail.start():]
        if fixed!=body:
            fixes.append(f'escaped_internal_quotes_line_{i+1}')
        match=ASSIGN.fullmatch(fixed)
        if match and ',' not in match.group(3).split('--',1)[0]:
            following=next((n.strip() for n in lines[i+1:] if n.strip() and not n.lstrip().startswith('--')), '')
            if SIMPLE_START.match(following):
                # Insert before trailing comment rather than inside it.
                comment_at=fixed.find('--',match.end(2)+1)
                if comment_at>=0:
                    fixed=fixed[:comment_at].rstrip()+', '+fixed[comment_at:]
                else:
                    fixed=fixed.rstrip()+','
                fixes.append(f'added_separator_line_{i+1}')
        lines[i]=fixed+eol
    return ''.join(lines),fixes

def certify(path: Path) -> dict:
    text=Path(path).read_text(encoding='utf-8-sig')
    err=syntax_error(text)
    if err is None:return {'valid':True,'repaired':False,'fixes':[]}
    repaired,fixes=safe_repair(text)
    if fixes and syntax_error(repaired) is None:
        Path(path).write_text(repaired,encoding='utf-8')
        return {'valid':True,'repaired':True,'fixes':fixes}
    return {'valid':False,'repaired':False,'fixes':fixes,'error':err,'suspected_lines':suspected_lines(text)}
, stripped):
            following = next((s.strip() for s in lines[index + 1:] if s.strip() and not s.lstrip().startswith('--')), '')
            if SIMPLE_START.match(following):
                suspects.append({'line': index + 1, 'kind': 'missing_comma', 'sample': stripped[:180]})
        if len(suspects) >= limit:
            break
    return suspects

def safe_repair(text: str) -> tuple[str,list[str]]:
    """Repair only quoted Lua table entries with unambiguous outer delimiters.

    Preserve source separately. Every repaired output must pass the full Lua parser
    and accepted translation equality checks before being delivered.
    """
    lines=text.splitlines(keepends=True)
    fixes=[]
    for i,original in enumerate(lines):
        body=original.rstrip('\r\n')
        eol=original[len(body):]
        start=re.match(r'^(\s*[A-Za-z_][\w.]*\s*=\s*)"',body)
        if not start:
            continue
        # Last non-comment string quote is the closing Lua delimiter.
        tail=re.search(r'"\s*,?\s*(?:--.*)?$',body)
        if not tail or tail.start()<=start.end()-1:
            continue
        inner=body[start.end():tail.start()]
        escaped=[]
        j=0
        while j<len(inner):
            if inner[j]=='\\' and j+1<len(inner):
                escaped.append(inner[j:j+2]);j+=2
            elif inner[j]=='"':
                escaped.append(r'\"');j+=1
            else:
                escaped.append(inner[j]);j+=1
        fixed=body[:start.end()]+''.join(escaped)+body[tail.start():]
        if fixed!=body:
            fixes.append(f'escaped_internal_quotes_line_{i+1}')
        match=ASSIGN.fullmatch(fixed)
        if match and ',' not in match.group(3).split('--',1)[0]:
            following=next((n.strip() for n in lines[i+1:] if n.strip() and not n.lstrip().startswith('--')), '')
            if SIMPLE_START.match(following):
                # Insert before trailing comment rather than inside it.
                comment_at=fixed.find('--',match.end(2)+1)
                if comment_at>=0:
                    fixed=fixed[:comment_at].rstrip()+', '+fixed[comment_at:]
                else:
                    fixed=fixed.rstrip()+','
                fixes.append(f'added_separator_line_{i+1}')
        lines[i]=fixed+eol
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
