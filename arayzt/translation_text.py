"""Data-only PZ TXT reader and strict Lua audit representation (never executes Lua).

PZ's Java reader uses the literal left side of '=' as the key. Bracket notation
belongs only in the Lua representation, never in the game's translation TXT.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

HEADER=re.compile(r'^\s*([A-Za-z_]\w*)\s*(=\s*)?\{\s*$')
ENTRY=re.compile(r'^\s*(?P<key>[^=\r\n]+?)\s*=\s*"(?P<value>.*)"\s*(?P<tail>\.\.,|\.\.|[,;]?\}|[,;]?)\s*$')
LONG_COMMENT=re.compile(r'--\[(=*)\[')
CONT=re.compile(r'^\s*"(?P<value>.*)"\s*(?P<tail>\.\.,|\.\.|[,;]?\}|[,;]?)\s*$')

@dataclass
class Document:
    header: str
    entries: dict
    comments: list
    warnings: list
    unsupported: list


def strip_comments(text):
    """Blank comments without moving positions; protect comment markers in strings."""
    chars=list(text);comments=[];i=0;quoted=False
    while i<len(text):
        if text[i]=='\n':quoted=False
        if text[i]=='\\' and quoted:
            i+=2;continue
        if text[i]=='"':quoted=not quoted;i+=1;continue
        if not quoted:
            end=None
            long_comment=LONG_COMMENT.match(text,i)
            if long_comment or text.startswith('/*',i):
                close=']'+long_comment[1]+']' if long_comment else '*/'
                start=long_comment.end() if long_comment else i+2
                at=text.find(close,start)
                if at<0:raise ValueError('Unterminated block comment')
                end=at+len(close)
            elif text.startswith('--',i):
                at=text.find('\n',i);end=len(text) if at<0 else at
            if end is not None:
                comments.append(text[i:end])
                for j in range(i,end):
                    if chars[j] not in '\r\n':chars[j]=' '
                i=end;continue
        i+=1
    return ''.join(chars),comments


def parse_native(text, *, strict=False):
    """Read our canonical PZ export exactly as Java does (no Lua unescaping)."""
    lines=text.splitlines();header=HEADER.fullmatch(lines[0].split(' -- AZT-native-v1')[0]) if lines else None
    entries={};bad=[];closed=False;comments=[]
    for n,line in enumerate(lines[1:],2):
        if line.strip()=='}':closed=True;continue
        if closed:continue # comments are archived after the table
        if not line.strip():continue
        m=ENTRY.fullmatch(line)
        if not m or m['tail']!=',':bad.append({'line':n,'kind':'invalid_native_entry'});continue
        entries[m['key'].strip()]=m['value']
    if not header or not closed:bad.append({'kind':'missing_table_delimiter'})
    if strict and bad:raise ValueError('Invalid canonical PZ translation: '+repr(bad))
    if closed:
        end=next(i for i,line in enumerate(lines) if line.strip()=='}')
        _,comments=strip_comments('\n'.join(lines[end+1:]))
    return Document(header[1] if header else 'Translation_PTBR',entries,comments,[],bad)


def parse(text, *, strict=False):
    if text.splitlines() and ' -- AZT-native-v1' in text.splitlines()[0]:
        return parse_native(text,strict=strict)
    from .core import lua_decode
    # Repair only explicitly supported legacy quote/delimiter defects; all
    # unrecognized statements remain fatal to export, never silently discarded.
    from .legacy_repair import repair_legacy
    original_clean,original_comments=strip_comments(text)
    if re.search(r'"[ \t]*\.\.[ \t]*[A-Za-z_0-9]',original_clean):
        raise ValueError('Unsupported nonliteral concatenation expression')
    normalized,fixes=repair_legacy(text)
    clean,comments=strip_comments(normalized)
    header=None;entries={};warnings=[];bad=[];pending=None;closed=False;attached_close=False
    for n,line in enumerate(clean.splitlines(),1):
        v=line.strip()
        if not v:continue
        h=HEADER.fullmatch(line)
        if h and header is None:
            header=h[1]
            if not h[2]:warnings.append({'kind':'missing_header_equals','line':n})
            continue
        if v in ('}', '},', '};'):
            if pending:bad.append({'line':n,'kind':'unterminated_concatenation'})
            closed=True;continue
        m=ENTRY.fullmatch(line) if pending is None else CONT.fullmatch(line)
        if not m or header is None or closed:
            bad.append({'line':n,'kind':'unsupported_statement','sample':v[:150]});continue
        attached_close=m['tail'].endswith('}')
        if attached_close:warnings.append({'kind':'attached_table_close_normalized','line':n})
        if m['tail']=='..,':warnings.append({'kind':'dangling_concat_before_delimiter','line':n})
        if pending is None:
            key=m['key'].strip()
            if key.startswith('["') and key.endswith('"]'):key=lua_decode(key[2:-2])
            if not key or any(c in key for c in '=\r\n{}'):
                bad.append({'line':n,'kind':'invalid_key'});continue
            pending=[key,'']
        pending[1]+=lua_decode(m['value'])
        if m['tail']!='..':
            key,value=pending
            if key in entries:warnings.append({'kind':'duplicate_key','key':key,'line':n})
            entries[key]=value;pending=None
    if pending:bad.append({'kind':'unterminated_concatenation'})
    if not header or not (closed or attached_close):bad.append({'kind':'missing_table_delimiter'})
    if strict and bad:raise ValueError('Unsupported translation syntax: '+repr(bad[:5]))
    return Document(header or 'Translation_PTBR',entries,original_comments,warnings+fixes,bad)


def serialize(doc, entries, *, lua=False):
    from .core import lua_encode
    # Preserve comment text as a safe Lua long comment; pick a delimiter which
    # cannot be closed by any comment, including embedded ']]' and '}'.
    comments='\n'.join(doc.comments)
    level=''
    while ']'+level+']' in comments:level+='='
    prefix=('--['+level+'[\n'+comments+'\n]'+level+']\n') if comments else ''
    lines=[doc.header+' = {'+('' if lua else ' -- AZT-native-v1')]
    for key,value in entries.items():
        if any(c in key for c in '=\r\n{}'):raise ValueError('Unsafe translation key: '+key)
        outkey=('["'+lua_encode(key)+'"]') if lua and (not re.fullmatch(r'[A-Za-z_]\w*',key,re.ASCII) or key in {'and','break','do','else','elseif','end','false','for','function','goto','if','in','local','nil','not','or','repeat','return','then','true','until','while'}) else key
        if not lua and ('\n' in value or '\r' in value):raise ValueError('Physical newline unsupported in canonical PZ value')
        encoded=lua_encode(value) if lua else value
        lines.append('    '+outkey+' = "'+encoded+'",')
    lines.append('}')
    # First line must be the header: the game unconditionally skips it.
    return '\n'.join(lines)+'\n'+prefix
