"""Agregações de auditoria para dashboard; nunca altera arquivos do jogo."""
from collections import Counter, defaultdict
from pathlib import Path


def matches(row, filters):
    terms = [s.strip().casefold() for s in (filters or '').split(',') if s.strip()]
    if not terms:
        return True
    stem = Path(row.get('file','')).stem.casefold()
    for suffix in ('_ptbr', '_en'):
        if stem.endswith(suffix): stem = stem[:-len(suffix)]
    return any(term == stem or term == row.get('file','').casefold() for term in terms)


def summarize(report, filters='', selected=None):
    rows = [r for r in report.get('rows', []) if matches(r, filters)]
    counts = Counter(r.get('status','unknown') for r in rows)
    by_file = defaultdict(lambda: Counter())
    for r in rows:
        by_file[r['file']][r.get('status','unknown')] += 1
    files = []
    for name, stats in by_file.items():
        files.append({'file': name, 'total':sum(stats.values()),
                      'translated':stats['translated'], 'missing':stats['missing'],
                      'identical':stats['identical'], 'placeholder_mismatch':stats['placeholder_mismatch']})
    files.sort(key=lambda x:(-x['missing'],-x['total'],x['file']))
    problems = [p for p in report.get('problems', []) if matches(p, filters)]
    problem_counts = dict(Counter(p.get('kind','unknown') for p in problems))
    total = len(rows)
    translated = counts['translated']
    return {'counts':dict(counts),'total':total,'translated_pct': round(100*translated/total,1) if total else 0,
            'pending_pct':round(100*counts['missing']/total,1) if total else 0,
            'problems':len(problems),'problem_counts':problem_counts,
            'files':files,'source_files':report.get('source_files',0),
            'parsed_files':report.get('parsed_files',0),
            'filters':filters,'selected':selected if selected is not None else 0}
