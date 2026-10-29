"""Conservative repairs for legacy PZ Lua localization syntax.

Works on export copies only. Validation using luaparser remains mandatory.
"""
import re

SPACED = re.compile(r'^(\s*)([A-Za-z_][\w]*(?:[\w ]*[\w])?)\s*=\s*(?=")')
QUOTED = re.compile(r'^(\s*(?:\["[^"]+"\]|[A-Za-z_][\w.]*)\s*=\s*)"(.*)"(\s*,?\s*(?:--.*)?)$')
CONT = re.compile(r'^\s*".*"(?:\s*\.\.\s*|\s*,?\s*)$')
COMMENTED_CONCAT = re.compile(r'^\s*--\s*[A-Za-z_]\w*\s*=\s*".*"\s*\.\.\s*$')

def repair_legacy(text: str):
    original_lines=text.splitlines(keepends=True)
    fixed=[];fixes=[];commented=False
    for index,line in enumerate(original_lines,1):
        core=line.rstrip('\r\n')
        ending=line[len(core):]
        trim=core.strip()
        if COMMENTED_CONCAT.match(core):
            commented=True
            fixed.append(line)
            continue
        if commented and CONT.match(core):
            fixed.append(re.match(r'^\s*',core).group()+'-- '+trim+ending)
            fixes.append({'line':index,'kind':'orphaned_commented_continuation'})
            if not trim.endswith('..'):commented=False
            continue
        commented=False
        if not trim or trim.startswith('--'):
            fixed.append(line);continue
        m=SPACED.match(core)
        if m:
            key=m.group(2).rstrip()
            if ' ' in key:
                prefix=m.group(1)+'["'+key+'"] = '
                core=prefix+core[m.end():]
                fixes.append({'line':index,'kind':'bracket_key','key':key})
        # Only repair a complete quoted entry; do not rewrite Lua string concatenations.
        m=QUOTED.match(core)
        if m:
            raw=m.group(2)
            # Quote all unescaped internal quote characters.
            safe=[];i=0
            while i<len(raw):
                if raw[i]=='\\' and i+1<len(raw):
                    if raw[i+1] in ('%',):
                        safe.append('\\\\'+raw[i+1])
                        fixes.append({'line':index,'kind':'invalid_escape'})
                    else:safe.append(raw[i:i+2])
                    i+=2
                elif raw[i]=='"':
                    safe.append('\\"')
                    fixes.append({'line':index,'kind':'internal_quote'})
                    i+=1
                else:
                    safe.append(raw[i]);i+=1
            core=m.group(1)+'"'+''.join(safe)+'"'+m.group(3)
            # Missing delimiter only when next significant line is a new entry.
            tail=m.group(3).split('--',1)[0]
            following=next((x.strip() for x in original_lines[index:]
                            if x.strip() and not x.lstrip().startswith('--')), '')
            if ',' not in tail and re.match(r'^(?:[A-Za-z_]\w*|\[")',following) and '=' in following:
                core=m.group(1)+'"'+''.join(safe)+'",'+m.group(3)
                fixes.append({'line':index,'kind':'missing_comma'})
        fixed.append(core+ending)
    return ''.join(fixed),fixes
