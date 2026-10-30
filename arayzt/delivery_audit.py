"""Delivery audit: distinguish proposed translations from bytes actually exported."""
import csv
import json
from pathlib import Path

COLUMNS = ['arquivo','chave','original_en','ptbr_antes','ptbr_depois','candidata',
           'responsavel','provedor','status','exportado','motivo',
           'tentativas_ollama','tentativas_analista','diagnostico_gerente','plano_correcao','historico']


def provenance(history, candidate, model=''):
    for event in reversed(history):
        if event.get('translation') != candidate:
            continue
        if event.get('agent') == 'analyst':
            return {'producer':'analyst','provider':event.get('provider','preset')}
        if event.get('agent') in ('translator','translator_ii'):
            return {'producer':event['agent'],'provider':model}
    return {'producer':'unknown','provider':''}


def save_delivery_audit(work, report, approved, reviews, errors, histories, exported):
    work=Path(work)
    candidates={(i['file'],i['key']):i for i in approved}
    pending={(i['file'],i['key']):i for i in reviews}
    failed={(i['file'],i['key']):i for i in errors}
    history_by_key={(i['file'],i['key']):i for i in histories}
    blocked={i['file'] for i in exported.get('blocked_files',[])}
    output=Path(exported['output'])
    file_ok={name: name not in blocked and not exported.get('export_error') and (output/name).is_file()
             for name in {r['file'] for r in report['rows']}}
    manifest_path=exported.get('manifest')
    delivered_map=None
    actual={}
    if manifest_path:
        manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        delivered_map={(i['file'],i['key']):i['translation'] for i in manifest['entries']}
        from .core import read_translation
        for name in {i['file'] for i in manifest['entries']}:
            try:actual[name]=read_translation(output/name)
            except (ValueError,OSError):actual[name]={}
    destination=work/'auditoria-traducao.csv'
    temporary=destination.with_suffix('.csv.tmp')
    with temporary.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=COLUMNS,delimiter=';',lineterminator='\r\n')
        writer.writeheader()
        for row in report['rows']:
            identity=(row['file'],row['key'])
            chosen=candidates.get(identity)
            review=pending.get(identity)
            error=failed.get(identity)
            record=history_by_key.get(identity,{})
            history=record.get('history',[])
            delivered=bool(chosen and file_ok[row['file']])
            if delivered and delivered_map is not None:
                delivered=(delivered_map.get(identity)==chosen['translation'] and actual.get(row['file'],{}).get(row['key'])==chosen['translation'])
            candidate=(chosen or review or {}).get('translation','')
            meta=provenance(history,candidate)
            if chosen:
                meta={'producer':chosen.get('producer',meta['producer']),
                      'provider':chosen.get('provider',meta['provider'])}
            if chosen and chosen.get('review_approved'):
                meta={'producer':'human','provider':'manual'}
            status=('approved' if delivered else 'approved_not_exported') if chosen else (
                'needs_review' if review else 'failed' if error else record.get('status',
                'original_ptbr' if row.get('ptbr') else 'not_processed'))
            reasons=(review or {}).get('reasons',[]) or record.get('reasons',[])
            if error:
                reasons=[error.get('error','translation_failed')]
            if chosen and not delivered:
                reasons=[exported.get('export_error') or 'file_blocked_or_not_exported']
            elif status=='not_processed':
                reasons=['outside_run_or_unsupported_source']
            managers=[h for h in history if h.get('agent')=='manager']
            producer=meta['producer']
            if not chosen and not review and not error and not history:
                producer='original_ptbr' if row.get('ptbr') else 'none'
            values={'arquivo':row['file'],'chave':row['key'],'original_en':row['en'],
                'ptbr_antes':row.get('ptbr') or '',
                'ptbr_depois':candidate if delivered else row.get('ptbr') or '',
                'candidata':candidate,'responsavel':producer,'provedor':meta['provider'],
                'status':status,'exportado':'sim' if delivered else 'nao','motivo':'; '.join(reasons),
                'tentativas_ollama':sum(h.get('agent') in ('translator','translator_ii') for h in history),
                'tentativas_analista':sum(h.get('agent')=='analyst' for h in history),
                'diagnostico_gerente':json.dumps([h.get('diagnosis') for h in managers if h.get('diagnosis')],ensure_ascii=False),
                'plano_correcao':' | '.join(h.get('context','') for h in managers if h.get('context')),
                'historico':json.dumps(history,ensure_ascii=False)}
            # Spreadsheet programs interpret formula-looking strings on opening.
            # Keep content visible, but make those values inert in the CSV.
            writer.writerow({k:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v
                             for k,v in values.items()})
    temporary.replace(destination)
    return destination
