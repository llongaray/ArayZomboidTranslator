"""Agentes ciclicos de traducao com feedback de gerente e supervisao baseada em regras."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import threading
import json
from .ollama import OllamaClient, translate_rows
from .validation import validate_candidate
from .core import tokens

MAX_CYCLES=3

def repair_diagnosis(row,candidate,reasons):
    expected=tokens(row['en']);actual=tokens(candidate or '')
    return {'arquivo':row['file'],'chave':row['key'],'original':row['en'][:1200],
            'falhas':list(reasons),'marcadores_esperados':dict(expected),
            'marcadores_ausentes':list((expected-actual).elements()),
            'marcadores_extras':list((actual-expected).elements()),
            'regra':'Corrigir a candidata usando o contexto da chave; preservar significado, nomes próprios revisados, formatação e marcadores. Não copiar este diagnóstico na resposta.'}


def manager_decision(status,reasons,cycle,max_cycles=MAX_CYCLES,*,candidate=None,previous_candidates=(),row=None):
    if status=="approved":
        return {"decision":"approve","reason":"supervisor_passed","context":""}
    # Nonrecoverable structural/source errors are rejected; ambiguous output goes to the analyst.
    terminal={'non_string','empty_source','nonempty_for_empty_source','structural_echo',
              'metadata_echo','unrestored_marker','invalid_source'}
    if any(reason in terminal for reason in reasons):
        return {"decision":"reject","reason":",".join(reasons),"context":""}
    if candidate and candidate.strip() and any(candidate.strip()==p.strip() for p in previous_candidates):
        return {"decision":"analyze","reason":"no_progress","context":",".join(reasons)}
    if cycle>=max_cycles:
        return {"decision":"analyze","reason":"max_cycles","context":",".join(reasons)}
    guide={"unchanged_english":"Traduza realmente o texto, sem deixar o original em ingles.",
           "id_prefix_echo":"Não inclua IDs internos como K1, prefixos ou separadores. Retorne somente a tradução dentro do campo do ID.",
           "suspected_english":"Corrija termos nao traduzidos para portugues brasileiro.",
           "glossary_mismatch":"Use rigorosamente o glossario de termos do jogo.",
           "placeholder_mismatch":"Mantenha todos os placeholders inalterados.",
           "structural_echo":"Nao retorne nomes de arquivos, identificadores ou chaves.",
           "metadata_echo":"Nunca retorne metadados ou estruturas JSON como traducao.",
           "empty_translation":"Forneca uma traducao nao vazia."}
    context=" ".join(guide.get(r,"Corrija o erro: "+r) for r in reasons)
    diagnosis=repair_diagnosis(row,candidate,reasons) if row else {}
    if diagnosis:
        context+=' Diagnóstico e plano: '+json.dumps(diagnosis,ensure_ascii=False)
    return {"decision":"retry","reason":",".join(reasons),"context":context[:2200],
            'diagnosis':diagnosis}

def translate_atom(row,url,model,cancel,on_stage=None,worker_id=None):
    history=[];feedback="";previous="";reasons=[]
    def stage(agent, cycle, **detail):
        if on_stage:
            on_stage(worker_id,row,agent,cycle,detail)
    for cycle in range(1,MAX_CYCLES+1):
        if cancel.is_set():
            return {"row":row,"status":"cancelled","translation":previous,"reasons":["cancelled"],"attempts":cycle-1,"history":history}
        from .core import likely_fixed
        if not row["en"].strip():
            return {"row":row,"status":"rejected","translation":"","reasons":["empty_source"],"attempts":0,"history":history}
        if likely_fixed(row["en"]) or row["en"].strip().casefold() in {"xbox","playstation","hotdog","taco","burrito","champagne","linear"}:
            state,reasons=validate_candidate(row["en"],row["en"],row["key"])
            if state=="approved":
                return {"row":row,"status":"approved","translation":row["en"],"reasons":[],"attempts":0,"history":[{"agent":"supervisor","cycle":0,"status":"approved","reasons":["invariant"]}]}
        from .context_glossary import CURATED, INVARIANT
        suggested=CURATED.get(row["key"])
        if suggested is not None:
            candidate_status,candidate_reasons=validate_candidate(row["en"],suggested,row["key"])
            if candidate_status=="approved":
                return {"row":row,"status":"approved","translation":suggested,"reasons":[],"attempts":0,"history":[{"agent":"supervisor","cycle":0,"status":"approved","reasons":["curated"]}]}
        if row["key"] in INVARIANT and row["en"].strip():
            return {"row":row,"status":"approved","translation":row["en"],"reasons":[],"attempts":0,"history":[{"agent":"supervisor","cycle":0,"status":"approved","reasons":["invariant_key"]}]}
        request=dict(row)
        if feedback:
            request["manager_feedback"]=feedback
            request["previous_translation"]=previous
        stage('translator',cycle)
        done,errors=translate_rows(OllamaClient(url,model),[request],batch_size=1,retries=0)
        if done:
            candidate=done[0]["translation"]
            status,reasons=validate_candidate(row["en"],candidate,row["key"])
        else:
            candidate="";status="rejected"
            reasons=[e.get("error","ollama_error") for e in errors] or ["ollama_error"]
        history.append({"agent":"translator","cycle":cycle,"translation":candidate})
        stage('supervisor',cycle)
        history.append({"agent":"supervisor","cycle":cycle,"status":status,"reasons":reasons})
        stage('manager',cycle,status=status,reasons=reasons)
        candidates=[h['translation'] for h in history if h['agent']=='translator']
        decision=manager_decision(status,reasons,cycle,candidate=candidate,previous_candidates=candidates[:-1])
        if decision['reason']=='no_progress':
            reasons=list(dict.fromkeys(reasons+['no_progress']))
        history.append({"agent":"manager","cycle":cycle,**decision})
        if decision["decision"]=="approve":
            return {"row":row,"status":"approved","translation":candidate,"reasons":[],"attempts":cycle,"history":history}
        if decision['decision']=='analyze':
            from .analyst import TranslationAnalyst
            result=TranslationAnalyst().analyze(row,candidate,reasons)
            history.append({'agent':'analyst','cycle':cycle,**result})
            return {'row':row,'status':'approved' if result['status']=='approved' else 'rejected','translation':result['translation'],'reasons':result['reasons'],'attempts':cycle,'history':history}
        feedback=decision["context"];previous=candidate
    return {"row":row,"status":"rejected","translation":previous,"reasons":reasons,"attempts":MAX_CYCLES,"history":history}

def orchestrate(rows,url,model,workers,cancel,on_result,on_stage=None):
    workers=max(1,min(int(workers),4))
    iterator=iter(rows)
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="aray-agent") as pool:
        active={}
        slots={}
        def submit(slot):
            if cancel.is_set():return
            try:row=next(iterator)
            except StopIteration:return
            active[pool.submit(translate_atom,row,url,model,cancel,on_stage,slot)]=(row,slot)
        for slot in range(1,workers+1):submit(slot)
        while active:
            finished,_=wait(active,return_when=FIRST_COMPLETED)
            for future in finished:
                row,slot=active.pop(future)
                try:result=future.result()
                except Exception as exc:
                    result={"row":row,"status":"rejected","translation":"","reasons":[str(exc)],"attempts":0,"history":[]}
                on_result(result)
                if on_stage:on_stage(slot,row,"complete",result.get("attempts",0),{"status":result["status"]})
                submit(slot)
