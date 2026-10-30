import argparse
import json
from pathlib import Path
from .core import audit, select_rows, export_overlay, write_json
from .ollama import OllamaClient, translate_rows
from .jobs import Pipeline


def execute(game, work, mode="all", model="gemma3:4b", batch=8, url="http://127.0.0.1:11434", translate=False, progress=None, files="", unsafe_review=False):
    work = Path(work).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    report = audit(Path(game))
    write_json(work / "audit.json", report)
    rows = select_rows(report, mode, files, unsafe_review)
    result = {"counts":report["counts"],"problems":len(report["problems"]),"selected":len(rows),"audit":str(work / "audit.json"),"filters":files,"problem_counts":report["problem_counts"],"parsed_files":report["parsed_files"],"source_files":report["source_files"]}
    if not translate: return result
    # Resumo de checkpoint: retoma somente traduções de chaves com o mesmo texto original.
    checkpoint = work / "checkpoint.json"
    memo = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {}
    pending = [r for r in rows if memo.get(json.dumps([r["file"],r["key"],r["en"]],ensure_ascii=False)) is None]
    accepted = []
    def save(batch_index, total, failed):
        if progress: progress(batch_index,total,failed)
    client = OllamaClient(url, model)
    # Um lote de cada vez para salvar checkpoints imediatamente.
    failures = []
    for start in range(0,len(pending),batch):
        current = pending[start:start+batch]
        done, errors = translate_rows(client,current,batch_size=batch,retries=2)
        accepted.extend(done);failures.extend(errors)
        for r in done:
            en = next(row["en"] for row in current if row["file"] == r["file"] and row["key"] == r["key"])
            memo[json.dumps([r["file"],r["key"],en],ensure_ascii=False)] = r["translation"]
        write_json(checkpoint,memo)
        save(min(start+len(current),len(pending)),len(pending),len(failures))
    for r in rows:
        match = memo.get(json.dumps([r["file"],r["key"],r["en"]],ensure_ascii=False))
        if match is not None:
            accepted.append({"file":r["file"],"key":r["key"],"translation":match,"source":r["status"]})
    # Remover duplicidades da lista de aceitos, preservando o resultado novo.
    accepted = list({(r["file"],r["key"]):r for r in accepted}.values())
    write_json(work / "accepted.json", {"translations":accepted,"failed":failures})
    result.update(export_overlay(report,accepted,work / "export",work / "backup"))
    result.update({"failed":len(failures),"checkpoint":str(checkpoint),"accepted":str(work / "accepted.json")})
    return result


def main():
    parser = argparse.ArgumentParser(description="Aray Zomboid Translator — B42 EN/PTBR")
    sub = parser.add_subparsers(dest="cmd",required=True)
    for name in ("audit","translate"):
        p = sub.add_parser(name)
        p.add_argument("--game",required=True,help="Raiz do jogo ou pasta Translate")
        p.add_argument("--work",default="./workspace")
        p.add_argument("--mode",choices=["missing","review","all"],default="all")
        p.add_argument("--model",default="gemma3:4b")
        p.add_argument("--batch",type=int,default=8)
        p.add_argument("--url",default="http://127.0.0.1:11434")
        p.add_argument("--files",default="",help="Ex.: UI,ContextMenu,Moodles")
        p.add_argument("--limit",type=int,default=0,help="Limite de entradas (0 para todas)")
        p.add_argument("--unsafe-review",action="store_true",help="Inclui textos existentes para revisão; exportação exige aprovação explícita")
    export = sub.add_parser("export",help="Reexportar checkpoint aprovado sem inferências")
    export.add_argument("--work",default="./workspace")
    web = sub.add_parser("dashboard")
    web.add_argument("--host",default="127.0.0.1")
    web.add_argument("--port",type=int,default=8767)
    args = parser.parse_args()
    if args.cmd == "export":
        from .delivery import reexport
        print(json.dumps(reexport(args.work),ensure_ascii=False,indent=2))
        return
    if args.cmd == "dashboard":
        from .web import app
        app.run(host=args.host,port=args.port,debug=False,threaded=True)
        return
    if args.batch < 1 or args.batch > 64: parser.error("--batch deve estar entre 1 e 64")
    res = Pipeline(lambda **state:print(json.dumps(state,ensure_ascii=False),flush=True) if "phase" in state else None).run(args.game,args.work,args.mode,args.model,args.batch,args.url,args.cmd=="translate",files=args.files,limit=args.limit)
    print(json.dumps(res,ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
