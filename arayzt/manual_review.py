"""Decisoes explicitas de revisao humana salvas fora do checkpoint da IA."""
import json
from pathlib import Path
from .core import tokens
from .validation import validate_candidate

def read_decisions(work):
    p=Path(work)/"manual-decisions.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}

def decision_id(file,key):
    return json.dumps([file,key],ensure_ascii=False)

def record_decision(work,file,key,translation,action):
    from .jobs import atomic_json
    if action not in ("approve","reject"):raise ValueError("Acao invalida")
    work=Path(work)
    audit=json.loads((work/"audit.json").read_text(encoding="utf-8"))
    row=next((r for r in audit["rows"] if r["file"]==file and r["key"]==key),None)
    if row is None:raise ValueError("Chave ausente na auditoria")
    if action=="approve":
        status,reasons=validate_candidate(row["en"],translation,key)
        if status=="rejected" or tokens(row["en"])!=tokens(translation):
            raise ValueError("Traducao invalida: "+",".join(reasons))
    decisions=read_decisions(work)
    decisions[decision_id(file,key)]={"file":file,"key":key,"translation":translation,"action":action}
    atomic_json(work/"manual-decisions.json",decisions)
    return decisions[decision_id(file,key)]

def pending_review(work):
    work=Path(work)
    path=work/"quality-review.json"
    if not path.is_file():return []
    data=json.loads(path.read_text(encoding="utf-8"))
    decisions=read_decisions(work)
    results=[]
    for item in data.get("needs_review",[]):
        out=dict(item)
        decision=decisions.get(decision_id(out["file"],out["key"]))
        if decision:
            out["decision"]=decision["action"]
            out["translation"]=decision["translation"]
        results.append(out)
    return results
