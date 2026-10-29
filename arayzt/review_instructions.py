"""Human instructions for pending translations, applied through local Ollama.

This module never edits game files. It records only validated output as a
manual decision; the normal export pipeline subsequently applies the changes.
"""
from __future__ import annotations
import json
from pathlib import Path
from .ollama import OllamaClient, translate_rows
from .validation import validate_candidate
from .manual_review import pending_review, record_decision

def instruct(work, file, instruction, model='gemma3:4b', url='http://127.0.0.1:11434', key=None, limit=20, on_progress=None):
    if not instruction or not instruction.strip() or len(instruction)>1200:
        raise ValueError('Instrução deve conter de 1 a 1200 caracteres')
    if not file or not file.strip():
        raise ValueError('Escolha o arquivo para revisão')
    items=[r for r in pending_review(work) if r['file']==file and
           (key is None or r['key']==key) and r.get('decision')!='approve']
    if not items:
        raise ValueError('Nenhuma pendência localizada no arquivo/chave solicitados')
    client=OllamaClient(url,model)
    results=[]
    for index,row in enumerate(items[:max(1,min(int(limit),50))],1):
        english=row.get('english','')
        previous=row.get('translation','')
        request={'file':file,'key':row['key'],'en':english,
                 'manager_feedback':('INSTRUÇÃO DO REVISOR HUMANO (prioritária, desde que preserve '
                  'o significado do texto original e todos os marcadores): '+instruction),
                 'previous_translation':previous}
        try:
            translated,failures=translate_rows(client,[request],batch_size=1,retries=0)
            if not translated:
                raise ValueError(str(failures)[:250])
            candidate=translated[0]['translation']
            status,reasons=validate_candidate(english,candidate,row['key'])
            if status!='approved':
                results.append({'key':row['key'],'status':'needs_review',
                                'translation':candidate,'reasons':reasons})
            else:
                record_decision(work,file,row['key'],candidate,'approve')
                results.append({'key':row['key'],'status':'approved','translation':candidate})
        except Exception as exc:
            results.append({'key':row['key'],'status':'failed','error':str(exc)[:300]})
        if on_progress:
            on_progress(index,len(items[:max(1,min(int(limit),50))]),results[-1])
    return {'file':file,'requested':len(items),'processed':len(results),
            'approved':sum(x['status']=='approved' for x in results),'items':results,
            'remaining':max(0,len(items)-len(results))}
