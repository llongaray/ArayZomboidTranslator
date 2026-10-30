"""Export pending human review to Excel-friendly UTF-8 CSV without modifying decisions."""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path

COLUMNS = ["arquivo", "chave", "original_en", "traducao_ptbr", "motivo_rh",
           "status", "ciclos", "historico_motivos"]

def report_rows(work: Path):
    work = Path(work)
    reviews = json.loads((work / "quality-review.json").read_text(encoding="utf-8"))
    entries = reviews.get("needs_review", [])
    history_path = work / "agent-history.json"
    histories = json.loads(history_path.read_text(encoding="utf-8")).get("items", []) if history_path.is_file() else []
    lookup = {(item["file"], item["key"]): item for item in histories}
    result = []
    for entry in entries:
        item = lookup.get((entry["file"], entry["key"]), {})
        attempts = [h for h in item.get("history", []) if h.get("agent") == "translator"]
        feedback = [str(reason) for h in item.get("history", []) if h.get("agent") == "supervisor"
                    for reason in h.get("reasons", [])]
        result.append({
            "arquivo": entry["file"],
            "chave": entry["key"],
            "original_en": entry.get("english", ""),
            "traducao_ptbr": entry.get("translation", ""),
            "motivo_rh": "; ".join(map(str, entry.get("reasons", []))),
            "status": entry.get("quality", "needs_review"),
            "ciclos": len(attempts),
            "historico_motivos": "; ".join(dict.fromkeys(feedback)),
        })
    return result

def report_csv(work: Path) -> str:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, delimiter=";", lineterminator="\r\n",
                            quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    writer.writerows(report_rows(work))
    # BOM helps Microsoft Excel read UTF-8 accents without mangling.
    return "\ufeff" + out.getvalue()

def save_report(work: Path) -> Path:
    destination = Path(work) / "relatorio-revisao-humana.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(report_csv(work).encode("utf-8"))
    return destination
