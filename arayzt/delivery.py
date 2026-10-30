"""Export-only resume: no model or translation worker is constructed."""
import json
from pathlib import Path
from .core import export_overlay, read_translation, tokens
from .jobs import atomic_json, fingerprint, load_memory
from .delivery_audit import save_delivery_audit
from .linguistic_audit import screen, reviewed_translation


def reexport(work, event=None):
    work=Path(work).expanduser().resolve();event=event or (lambda **kw:None)
    report=load_memory(work/'audit.json');saved=load_memory(work/'accepted.json')
    approved=saved.get('translations',[])
    if not approved:raise ValueError('No approved translations available for export')
    rows={(r['file'],r['key']):r for r in report['rows']}
    memory=load_memory(work/'checkpoint-v040.json')
    histories=load_memory(work/'agent-history.json').get('items',[])
    by_history={(r['file'],r['key']):r for r in histories}
    sources={}
    # Check against current EN, not just a cached audit, before reusing approval.
    for item in approved:
        row=rows[(item['file'],item['key'])]
        path=Path(report['game'])/'EN'/row['en_file']
        if path not in sources:sources[path]=read_translation(path)
        if sources[path].get(row['key'])!=row['en']:
            raise ValueError('EN changed; export-only resume requires a fresh audit: '+row['key'])
        cached=memory.get(fingerprint(row))
        if not isinstance(cached,dict) or cached.get('quality')!='approved' or cached.get('translation')!=item['translation']:
            raise ValueError('Approved checkpoint mismatch: '+row['key'])
    audit=screen(report,approved)
    # Persist the original diagnosis before any correction is applied.
    audit_path=work/'linguistic-audit.json'
    previous=load_memory(audit_path)
    if previous.get('bodyparts_review'):
        audit['previous_bodyparts_review']=previous.get('previous_bodyparts_review',previous['bodyparts_review'])
    audit['contextual_changes']=list(previous.get('contextual_changes',[]))
    identities={(c['file'],c['key']) for c in audit['contextual_changes']}
    for reviewed in audit.get('previous_bodyparts_review',[]):
        if reviewed.get('changed') and (reviewed['file'],reviewed['key']) not in identities:
            audit['contextual_changes'].append({'file':reviewed['file'],'key':reviewed['key'],'en':reviewed['en'],'before':reviewed['before'],'after':reviewed['reviewed']})
    atomic_json(audit_path,audit)
    corrected=0
    for item in approved:
        identity=(item['file'],item['key']);row=rows[identity]
        value=reviewed_translation(row)
        if value is None or value==item['translation']:continue
        if tokens(value)!=tokens(row['en']):raise ValueError('Linguistic correction altered placeholders')
        before=item['translation']
        audit.setdefault('contextual_changes',[]).append({'file':item['file'],'key':item['key'],'en':row['en'],'before':before,'after':value})
        record=by_history.get(identity)
        if record is None:
            record={'file':item['file'],'key':item['key'],'history':[]};histories.append(record);by_history[identity]=record
        record['status']='approved';record['reasons']=[]
        record['history'].append({'agent':'analyst','cycle':0,'status':'approved','translation':value,
            'previous_translation':before,'provider':'linguistic-review:context-v1',
            'actions':['contextual_linguistic_review'],'reasons':[]})
        item.update(translation=value,producer='analyst',provider='linguistic-review:context-v1')
        cached=memory[fingerprint(row)]
        cached.update(translation=value,producer=item['producer'],provider=item['provider'],history=record['history'])
        corrected+=1
    if corrected:
        import shutil, uuid
        backup=work/'export-snapshots'/uuid.uuid4().hex
        backup.mkdir(parents=True)
        for name in ('checkpoint-v040.json','accepted.json','agent-history.json'):
            if (work/name).is_file():shutil.copy2(work/name,backup/name)
        atomic_json(work/'checkpoint-v040.json',memory)
        atomic_json(work/'accepted.json',saved)
        atomic_json(work/'agent-history.json',{'items':histories})
    event(phase='export',exported_entries=0,approved_unexported=len(approved),blocked_file_count=0,delivery_status='pending',accepted=len(approved),total=len(approved),progress=len(approved),percent=100,
          reused=len(approved),failed=0,needs_review=0,analyst_pending=0,message='Exportando checkpoint aprovado, sem inferências')
    result=export_overlay(report,approved,work/'export',work/'backup')
    csv=save_delivery_audit(work,report,approved,saved.get('needs_review',[]),saved.get('failed',[]),histories,result)
    result.update(audit=str(work/'audit.json'),selected=len(approved),processed=len(approved),reused=len(approved),
        approved_entries=len(approved),linguistic_corrections=corrected,linguistic_audit=str(audit_path),
        delivery_audit_csv=str(csv),failed=len(saved.get('failed',[])),checkpoint=str(work/'checkpoint-v040.json'))
    atomic_json(work/'export-diagnostics.json',result)
    result['export_diagnostics']=str(work/'export-diagnostics.json')
    audit['contextual_corrections_applied']=corrected
    audit['remaining_screening_findings']=[f for f in audit['findings'] if f.get('automatic_correction') is None]
    atomic_json(audit_path,audit)
    event(phase='done' if result['delivery_status']=='success' else 'export_partial',
          exported_entries=result['exported_entries'],approved_unexported=result['approved_unexported'],
          blocked_file_count=result['blocked_file_count'],delivery_status=result['delivery_status'],
          message='Entrega validada' if result['delivery_status']=='success' else 'Entrega parcial; há aprovações sem exportar')
    return result
