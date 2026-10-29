"""Auditoria determinística, exportação sem tocar nos arquivos do jogo."""
from __future__ import annotations
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Tokens que não devem ser alterados por um tradutor.
TOKEN_RE = re.compile(r"(?<!\d)%(?:\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[sdif]|(?<!\d)%\d+|\{[A-Za-z_][\w.:-]*\}|\$\{[^{}]+\}|<[^<>]+>|\\[nrt]|\[/?(?:color|img|icon|b|i)[^\]]*\]", re.I)
WORD_RE = re.compile(r"[A-Za-z]{3,}")


def tokens(s: str) -> Counter:
    return Counter(TOKEN_RE.findall(s))


def protect(s: str):
    mapping = {}
    def replace(m):
        marker = f"⟦AZT{len(mapping):04d}⟧"
        mapping[marker] = m.group()
        return marker
    return TOKEN_RE.sub(replace, s), mapping


def restore(value: str, mapping: dict) -> str:
    for marker, original in mapping.items():
        if value.count(marker) != 1:
            raise ValueError(f"Marcador ausente/duplicado: {marker}")
        value = value.replace(marker, original)
    return value


def object_pairs(pairs):
    out = {}
    for key, val in pairs:
        if key in out:
            raise ValueError(f"Chave JSON duplicada: {key}")
        out[key] = val
    return out


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=object_pairs)
    if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in data.items()):
        raise ValueError(f"JSON esperado: objeto plano de strings: {path}")
    return data


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Formato legado Lua: chaves por linha, preservando os demais comentários e espaços.
LUA_ENTRY_RE = re.compile(r'(?m)^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][\w.]*)[ \t]*=[ \t]*"(?P<value>(?:\\.|[^"\\])*)"\s*,?[^\S\r\n]*(?:--[^\r\n]*)?$')

def lua_decode(value: str) -> str:
    # Apenas decodificação de escape de aspas e barras; outros escapes ficam intactos.
    return value.replace(r'\"', '"').replace(r'\\', '\\')

def lua_encode(value: str) -> str:
    return value.replace('\\', r'\\').replace('"', r'\"').replace('\r', r'\r').replace('\n', r'\n')

def parse_lua(path: Path):
    """Lê entradas por linha; última definição prevalece, sem descartar o arquivo.

    Registra duplicidades e linhas de atribuição não reconhecidas para revisão.
    Não executa Lua e não tenta interpretar expressões arbitrárias.
    """
    text = path.read_text(encoding='utf-8-sig')
    result, warnings = {}, []
    matches = list(LUA_ENTRY_RE.finditer(text))
    for m in matches:
        key = m.group('key')
        if key in result:
            warnings.append({'kind': 'duplicate_key', 'key': key, 'line': text.count('\n', 0, m.start()) + 1})
        result[key] = lua_decode(m.group('value'))
    covered_lines = {text.count('\n', 0, m.start()) + 1 for m in matches}
    # Cabeçalhos/fechamentos Lua e linhas multilinha não são erros de atribuição.
    table_headers = re.compile(r'^\s*[A-Za-z_][\w.]*\s*=\s*\{\s*(?:--.*)?$')
    for n, line in enumerate(text.splitlines(), 1):
        if n in covered_lines or line.lstrip().startswith('--'): continue
        if re.match(r'^\s*[A-Za-z_][\w.]*\s*=', line) and not table_headers.match(line):
            warnings.append({'kind': 'unparsed_assignment', 'line': n, 'sample': line.strip()[:120]})
    if not result: raise ValueError(f'Nenhuma entrada Lua encontrada: {path}')
    return result, warnings

def read_lua(path: Path) -> dict:
    return parse_lua(path)[0]

def read_translation(path: Path) -> dict:
    return read_json(path) if path.suffix.lower() == '.json' else read_lua(path)

def translation_rel(filename: Path) -> Path:
    name = filename.name
    for suffix in ('_EN.txt', '_EN.json'):
        if name.endswith(suffix):
            return filename.with_name(name[:-len(suffix)] + '_PTBR' + filename.suffix)
    return filename

def is_free_text(relative: Path) -> bool:
    return relative.suffix.lower() == '.txt' and not relative.stem.upper().endswith(('_EN', '_PTBR'))

def likely_fixed(value: str) -> bool:
    v=value.strip()
    # Itens com mesmos caracteres em ambos os idiomas podem ser nomes próprios,
    # siglas, termos já internacionais ou sequências só de placeholders.
    return not v or not WORD_RE.search(v) or v.casefold() in {'central', 'chili', 'radio', 'normal', 'pizza', 'salami', 'steam', 'cocktail'}


def write_lua_overlay(path: Path, source: Path, english_source: Path, changes: dict):
    if source.is_file():
        text = source.read_text(encoding='utf-8-sig')
        from .lua_syntax import syntax_error, safe_repair
        if syntax_error(text):
            from .legacy_repair import repair_legacy
            normalized, repairs = repair_legacy(text)
            # Keep independently safe normalizations even when other legacy
            # syntax defects remain; the finished overlay must pass certify().
            if repairs:
                text = normalized
            repaired, fixes = safe_repair(text)
            if fixes:
                text = repaired
    else:
        # Criar arquivo compatível com o nome da tabela inglesa, porém sem copiar
        # automaticamente entradas ainda não traduzidas.
        original = english_source.read_text(encoding='utf-8-sig')
        head = re.search(r'(?m)^\s*([A-Za-z_][\w]*)\s*=\s*\{', original)
        if not head: raise ValueError(f'Cabeçalho Lua não reconhecido: {english_source}')
        header = head.group(1).replace('_EN','_PTBR')
        text = header + ' = {\n}\n'
    found=set()
    def replacer(m):
        key=m.group('key')
        if key not in changes:return m.group(0)
        found.add(key)
        old=m.group(0)
        # preservar indentação, comentário, vírgula e espaçamento após string
        prefix=old[:old.index('"')+1]
        suffix=old[old.rindex('"'):]
        return prefix+lua_encode(changes[key])+suffix
    # Em chaves duplicadas a última definição é a efetiva; alterar somente ela.
    matches = list(LUA_ENTRY_RE.finditer(text))
    last = {m.group('key'): m.start() for m in matches}
    def replace_last(m):
        if m.group('key') not in changes or last[m.group('key')] != m.start():
            return m.group(0)
        return replacer(m)
    text=LUA_ENTRY_RE.sub(replace_last,text)
    missing={k:v for k,v in changes.items() if k not in found}
    if missing:
        pos=text.rfind('}')
        if pos < 0: raise ValueError(f'Fechamento Lua não encontrado: {source}')
        indent='    '
        m=LUA_ENTRY_RE.search(text)
        if m: indent=m.group('indent') or indent
        extra=''.join(f'{indent}{k} = "{lua_encode(v)}",\n' for k,v in missing.items())
        text=text[:pos]+extra+text[pos:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    # Validar o overlay antes de indicar sucesso.
    parsed=read_lua(path)
    if any(parsed.get(k)!=v for k,v in changes.items()):
        path.unlink(missing_ok=True)
        raise ValueError(f'Falha na validação Lua: {path}')

def translation_root(game: Path) -> Path:
    game = game.expanduser().resolve()
    direct = game / "media/lua/shared/Translate"
    if direct.is_dir(): return direct
    if game.name.lower() == "translate" and (game / "EN").is_dir(): return game
    raise FileNotFoundError(f"Não encontrei media/lua/shared/Translate em {game}")


def audit(game: Path) -> dict:
    root = translation_root(Path(game))
    en_dir, pt_dir = root / 'EN', root / 'PTBR'
    if not en_dir.is_dir(): raise FileNotFoundError(f'Pasta EN ausente: {en_dir}')
    sources = sorted(p for p in en_dir.rglob('*') if p.is_file() and p.suffix.lower() in ('.json','.txt'))
    if not sources: raise ValueError(f'Nenhum arquivo JSON/TXT encontrado em {en_dir}')
    rows, problems, free_text, processed = [], [], [], 0
    for source in sources:
        relative = source.relative_to(en_dir)
        target_relative = translation_rel(relative)
        target = pt_dir / target_relative
        try:
            if is_free_text(relative):
                original = source.read_text(encoding='utf-8-sig')
                localized = target.read_text(encoding='utf-8-sig') if target.exists() else None
                free_text.append({'file': target_relative.as_posix(), 'en_file': relative.as_posix(),
                                  'status': 'missing' if localized is None else ('identical' if original == localized else 'translated'),
                                  'en': original, 'ptbr': localized})
                continue
            if source.suffix.lower() == '.txt':
                en, en_warnings = parse_lua(source)
                pt, pt_warnings = parse_lua(target) if target.is_file() else ({}, [])
                for warning in en_warnings: problems.append({'file':relative.as_posix(), 'severity':'warning', **warning})
                for warning in pt_warnings: problems.append({'file':target_relative.as_posix(), 'severity':'warning', **warning})
            else:
                en = read_json(source)
                pt = read_json(target) if target.is_file() else {}
            processed += 1
            for key, english in en.items():
                portuguese = pt.get(key)
                if portuguese is None or not portuguese.strip(): status='missing'
                elif tokens(english)!=tokens(portuguese): status='placeholder_mismatch'
                elif portuguese==english and bool(WORD_RE.search(english)): status='identical'
                else: status='translated'
                rows.append({'file':target_relative.as_posix(), 'en_file':relative.as_posix(),
                             'key':key, 'en':english, 'ptbr':portuguese, 'status':status})
            for extra in pt.keys()-en.keys():
                problems.append({'file':target_relative.as_posix(),'kind':'extra_ptbr_key','key':extra,'severity':'info'})
        except (ValueError,OSError) as exc:
            problems.append({'file':relative.as_posix(),'kind':'invalid_translation','error':str(exc),'severity':'error'})
    if not rows: raise ValueError(f'Nenhuma chave Lua/JSON analisada em {en_dir}; confira os erros')
    counts = dict(Counter(r['status'] for r in rows))
    return {'game':str(root),'timestamp':datetime.now(timezone.utc).isoformat(),
            'counts':counts,'rows':rows,'problems':problems,'free_text':free_text,
            'source_files':len(sources),'parsed_files':processed,
            'problem_counts':dict(Counter(p['kind'] for p in problems))}

# Grupos deliberadamente não automatizados: nomes próprios e texto que exige revisão humana.
PROTECTED_FILES = {'survivornames', 'survivorname', 'recorded_media', 'radiodata'}

def select_rows(report: dict, mode: str, files: str = '', unsafe_review: bool = False) -> list:
    """Seleciona apenas entradas ausentes, a menos que haja opt-in explícito para revisão.

    `all` continua realizando auditoria completa, mas NÃO sobrescreve PTBR existente.
    Filtro aceita nomes de arquivos separados por vírgulas, sem sufixo de idioma.
    """
    patterns = [p.strip().casefold() for p in files.split(',') if p.strip()]
    statuses = {'missing'} | ({'identical', 'placeholder_mismatch'} if unsafe_review and mode in ('all', 'review') else set())
    selection = []
    for row in report['rows']:
        stem = Path(row['file']).stem.casefold().removesuffix('_ptbr')
        if stem in PROTECTED_FILES or stem.startswith('survivornames'):
            continue
        if patterns and not any(p == stem or p == row['file'].casefold() for p in patterns):
            continue
        if row['status'] not in statuses:
            continue
        # Blank English entries have no material to translate.
        if not row['en'].strip():
            continue
        if row['status'] == 'identical' and likely_fixed(row['en']):
            continue
        selection.append(row)
    return selection


def export_overlay(report: dict, accepted: dict, output: Path, backup_dir: Path | None = None) -> dict:
    """Gera arquivos PTBR sem modificar os originais do jogo."""
    root = Path(report['game'])
    target_root = Path(output).resolve() / 'media/lua/shared/Translate/PTBR'
    if root in target_root.parents or target_root == root or root == Path(output).resolve() or Path(output).resolve().is_relative_to(root):
        raise ValueError('A saída deve ficar fora da instalação do jogo')
    grouped = {}
    for row in report['rows']: grouped.setdefault(row['file'], []).append(row)
    accepted_map = {(r['file'],r['key']):r for r in accepted}
    count=0; written=0; blocked=[];preexisting_warnings=[]
    for relative, rows in grouped.items():
        source_file=root/'PTBR'/relative
        changes={}
        for r in rows:
            item=accepted_map.get((relative,r['key']))
            if not item:continue
            value=item['translation']
            from .validation import validate_candidate
            quality, reasons = validate_candidate(r['en'],value,r['key'])
            if quality=='rejected' or not isinstance(value,str) or not value.strip() or tokens(r['en'])!=tokens(value):
                raise ValueError(f'Tradução inválida: {relative}/{r["key"]}')
            if r['status']=='translated':continue
            if r['status'] in {'identical','placeholder_mismatch'} and not item.get('review_approved',False):
                continue
            changes[r['key']]=value
        if not changes:continue
        if backup_dir and source_file.exists():
            destination=Path(backup_dir).resolve()/'PTBR'/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source_file,destination)
        output_file=target_root/relative
        if source_file.suffix.lower()=='.json':
            merged=read_json(source_file) if source_file.exists() else {}
            merged.update(changes)
            write_json(output_file,merged)
        else:
            en_source=root/'EN'/rows[0]['en_file']
            try:
                write_lua_overlay(output_file,source_file,en_source,changes)
                from .validation import validate_lua_comparative
                comparison=validate_lua_comparative(output_file,source_file,changes)
                from .lua_syntax import certify
                certification=certify(output_file)
                recovery=None
                if not certification['valid'] and source_file.exists():
                    from .lua_rebuild import recover
                    rebuilt,recovery=recover(source_file.read_text(encoding='utf-8-sig'),changes)
                    if recovery.get('valid'):
                        output_file.write_text(rebuilt,encoding='utf-8')
                        certification=certify(output_file)
                problems=[] if recovery and recovery.get('valid') else list(comparison['introduced'])
                if not certification['valid']:
                    problems.append({'kind':'lua_syntax_invalid',
                                     'error':certification['error'],
                                     'suspected_lines':certification.get('suspected_lines',[]),
                                     'attempted_fixes':certification.get('fixes',[])})
                if certification['valid']:
                    # A repaired file must still preserve every accepted translation.
                    parsed=read_lua(output_file)
                    if any(parsed.get(k)!=v for k,v in changes.items()):
                        problems.append(('repaired_file_mutated_translation',str(relative)))
                    if recovery and recovery.get('valid'):
                        original_entries=read_lua(source_file)
                        if any(parsed.get(k)!=v for k,v in original_entries.items() if k not in changes):
                            problems.append(('recovery_lost_original_translation',str(relative)))
                if comparison['preexisting']:
                    preexisting_warnings.append({'file':str(relative),'count':len(comparison['preexisting']),'examples':comparison['preexisting'][:5]})
                if problems:
                    quarantine=Path(output).resolve().parent/'quarantine'/'PTBR'/relative
                    quarantine.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(output_file,quarantine)
                    output_file.unlink(missing_ok=True)
                    blocked.append({'file':str(relative),'issues':problems[:20],
                                    'issue_count':len(problems),'candidate_file':str(quarantine)})
                    continue
            except ValueError as exc:
                output_file.unlink(missing_ok=True)
                blocked.append({'file':str(relative),'issues':[str(exc)],'issue_count':1})
                continue
        written+=1;count+=len(changes)
    return {'translated':count,'output':str(target_root),'files':written,'blocked_files':blocked,'preexisting_warnings':preexisting_warnings,'delivery_status':'partial' if blocked else 'success'}
