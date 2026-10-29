"""Independent pipeline stages: multiple translator workers + supervisor + manager.

Queues overlap: the translator never waits for supervisor/manager on another item.
Only the manager completes a work item or returns feedback to translation.
"""
from queue import Queue
from threading import Thread, Lock
from .agents import manager_decision, MAX_CYCLES
from .ollama import OllamaClient, translate_rows
from .validation import validate_candidate

def orchestrate_pipeline(rows,url,model,workers,cancel,on_result,on_stage=None):
    workers=max(1,min(int(workers),4))
    translation=Queue();supervision=Queue();management=Queue()
    lock=Lock()
    left=len(rows)
    def emit(slot,row,agent,cycle,detail=None):
        if on_stage:on_stage(slot,row,agent,cycle,detail or {})
    def finish(job,status,reasons):
        nonlocal left
        row=job['row']
        result={'row':row,'status':status,'translation':job.get('candidate',''),
                'reasons':reasons,'attempts':job['cycle'],'history':job['history']}
        with lock:
            on_result(result)
            left-=1
        emit(job.get('slot',0),row,'complete',job['cycle'],{'status':status})
    def translator(slot):
        client=OllamaClient(url,model)
        while True:
            job=translation.get()
            try:
                if job is None:return
                row=job['row'];job['slot']=slot
                if cancel.is_set():
                    finish(job,'cancelled',['cancelled']);continue
                emit(slot,row,'translator',job['cycle'])
                request=dict(row,status=row.get('status','missing'))
                if job['feedback']:
                    request['manager_feedback']=job['feedback']
                    request['previous_translation']=job.get('candidate','')
                try:
                    output,errors=translate_rows(client,[request],batch_size=1,retries=0)
                    candidate=output[0]['translation'] if output else ''
                    fault=[] if output else [x.get('error','ollama_error') for x in errors]
                except Exception as exc:
                    candidate='';fault=[str(exc)[:250]]
                job['candidate']=candidate;job['fault']=fault
                job['history'].append({'agent':'translator','cycle':job['cycle'],
                                       'translation':candidate})
                supervision.put(job)
            finally:translation.task_done()
    def supervisor():
        while True:
            job=supervision.get()
            try:
                if job is None:return
                row=job['row']
                emit(workers+1,row,'supervisor',job['cycle'])
                if job['fault']:
                    status='rejected';reasons=job['fault']
                else:
                    status,reasons=validate_candidate(row['en'],job['candidate'],row['key'])
                job['status']=status;job['reasons']=reasons
                job['history'].append({'agent':'supervisor','cycle':job['cycle'],
                                       'status':status,'reasons':reasons})
                management.put(job)
            finally:supervision.task_done()
    def manager():
        while True:
            job=management.get()
            try:
                if job is None:return
                row=job['row']
                emit(workers+2,row,'manager',job['cycle'])
                decision=manager_decision(job['status'],job['reasons'],job['cycle'])
                job['history'].append({'agent':'manager','cycle':job['cycle'],**decision})
                if cancel.is_set():
                    finish(job,'cancelled',['cancelled'])
                elif decision['decision']=='approve':
                    finish(job,'approved',[])
                elif decision['decision']=='retry' and job['cycle']<MAX_CYCLES:
                    job['feedback']=decision['context']
                    job['cycle']+=1
                    translation.put(job)
                else:
                    finish(job,'needs_review',job['reasons'])
            finally:management.task_done()
    for row in rows:
        job={'row':row,'cycle':1,'feedback':'','candidate':'',
             'fault':[],'history':[]}
        # Orchestrator verifies existing PTBR before spending LLM time:
        # identical or placeholder-drifted entries go to supervisor directly.
        if row.get('status') in ('identical','placeholder_mismatch') and row.get('ptbr'):
            job['candidate']=row['ptbr']
            supervision.put(job)
        else:
            translation.put(job)
    threads=[Thread(target=translator,args=(i,),daemon=True) for i in range(1,workers+1)]
    threads += [Thread(target=supervisor,daemon=True),Thread(target=manager,daemon=True)]
    for t in threads:t.start()
    # The manager is the sole owner of completion and retrial decisions.
    while True:
        with lock:
            if left==0:break
        from time import sleep
        sleep(.04)
    for _ in range(workers):translation.put(None)
    supervision.put(None);management.put(None)
    for t in threads:t.join(timeout=5)
