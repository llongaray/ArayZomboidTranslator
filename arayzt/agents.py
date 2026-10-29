"""Orquestrador de traducao atomica; workers concorrentes, supervisor e gerente.

Cada unidade e uma entrada. Somente a thread orquestradora persiste checkpoints,
evitando corrupcao e garantindo retomada por fingerprint.
"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from .ollama import OllamaClient, translate_rows
from .validation import validate_candidate

def translate_atom(row, url, model, cancel):
    if cancel.is_set():
        return {"row": row, "status": "cancelled", "translation": "", "reasons": ["cancelled"], "attempts": 0}
    client = OllamaClient(url, model)
    failures = []
    for attempt in range(2):
        if cancel.is_set():
            return {"row": row, "status": "cancelled", "translation": "", "reasons": ["cancelled"], "attempts": attempt}
        # Translator: one isolated generation per atomic entry.
        done, errors = translate_rows(client, [row], batch_size=1, retries=0)
        if done:
            candidate = done[0]["translation"]
            # Supervisor: structural and language heuristics.
            status, reasons = validate_candidate(row["en"], candidate, row["key"])
            if status == "approved":
                return {"row":row,"status":status,"translation":candidate,"reasons":[],"attempts":attempt+1}
            failures.append((status,candidate,reasons))
        else:
            failures.append(("rejected","", [str(e.get("error","ollama_error")) for e in errors]))
        # Manager: one bounded rework attempt, then escalate to human review.
    if failures:
        status, candidate, reasons = failures[-1]
        if status == "rejected" and not candidate:
            return {"row":row,"status":"rejected","translation":"","reasons":reasons,"attempts":2}
        return {"row":row,"status":"needs_review","translation":candidate,"reasons":reasons or ["supervisor_escalation"],"attempts":2}
    return {"row":row,"status":"rejected","translation":"","reasons":["no_result"],"attempts":2}

def orchestrate(rows, url, model, workers, cancel, on_result):
    """Bounded outstanding tasks; commits in the calling thread as results complete."""
    workers=max(1,min(int(workers),4))
    it=iter(rows)
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="aray-agent") as pool:
        active={}
        def submit():
            if cancel.is_set():return False
            try:row=next(it)
            except StopIteration:return False
            active[pool.submit(translate_atom,row,url,model,cancel)]=row
            return True
        for _ in range(workers):submit()
        while active:
            finished,_=wait(active,return_when=FIRST_COMPLETED)
            for future in finished:
                row=active.pop(future)
                try:result=future.result()
                except Exception as exc:
                    result={"row":row,"status":"rejected","translation":"","reasons":[str(exc)],"attempts":1}
                on_result(result)
                submit()
