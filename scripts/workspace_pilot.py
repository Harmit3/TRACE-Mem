"""Run the frozen internal Workspace pilot. Only the scorer reads answer keys."""
from contextlib import closing
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import json
import sys
from random import Random
from uuid import UUID
from unittest.mock import patch

from trace_mem.workspace import server
from trace_mem.workspace_chat import PREFERRED, structured_claim

ROOT = Path(__file__).resolve().parents[1] / "research/workspace40"
MODES = ["standard","rag","trace"]


def run():
    fixture = json.loads((ROOT/"inputs.json").read_text())
    rows, extracts, checks = [], [], {}
    rng = Random(23)
    with patch("trace_mem.workspace.uuid4",side_effect=lambda:UUID(int=rng.getrandbits(128))), TemporaryDirectory() as tmp, server(Path(tmp)/"memory.json",0) as app:
        store = app.store
        for key,value,start in fixture["facts"]:
            prior = [r for r in store.rows if r["key"]==key]
            store.save(key,value,start,replaces=prior[-1]["id"] if prior else None)
        before = list(store.rows)
        try:
            store.save(*fixture["ambiguous"])
        except ValueError:
            pass
        checks["incorrect_overwrites"] = int(before != store.rows)
        app.chats.invalidate()
        store.forget("badge")
        for text in fixture["extract"]:
            start = perf_counter()
            try:
                claim, usage = structured_claim(app.opener,PREFERRED,text,date(2025,3,1))
                value = [claim.predicate,claim.value,claim.intent] if claim else None
                extracts.append(dict(prediction=value,**usage))
            except Exception as exc:
                extracts.append(dict(error=type(exc).__name__,seconds=perf_counter()-start))
        for i,(qid,question,day) in enumerate(fixture["queries"]):
            for mode in MODES[i%3:]+MODES[:i%3]:
                chat = app.chats.action("new",{})["chat"]
                with closing(app.chats.connect()) as db, db:
                    db.executemany("INSERT INTO turns(chat,question,answer) VALUES(?,?,?)",
                        [(chat,f"Map exercise {n}: "+"draw fictional islands "*85,"Exercise recorded.") for n in range(24)])
                p = dict(chat=chat,model=PREFERRED,question=question+" Answer with just the value, or UNKNOWN if unavailable.",
                         output=48,temperature=0,budget=512,strategy=mode,verification=0,structured=False)
                chunks = []
                start = perf_counter()
                row = dict(mode=mode,query=qid)
                try:
                    result = app.chats.generate(p,store,app.opener,lambda event:chunks.append(event["text"]),date.fromisoformat(day))
                    row.update(answer="".join(chunks),retrieved=[r["value"] for r in result["evidence"]],
                               prompt=result["prompt"],output=result["output"],history=result["history"])
                except Exception as exc:
                    row["error"] = type(exc).__name__
                row["seconds"] = round(perf_counter()-start,3)
                rows.append(row)
                print(mode,qid,row.get("answer",row.get("error")),flush=True)
    return dict(rows=rows,extraction=extracts,engineering=checks)


def score(report):
    gold = json.loads((ROOT/"scoring.json").read_text())
    for row in report["rows"]:
        expected = gold[row["query"]] or "UNKNOWN"
        answer = row.get("answer","").strip().rstrip(".!").casefold()
        row.update(correct=answer==expected.casefold(),abstained=answer=="unknown",
                   hits=int(expected in row.get("retrieved",[])),
                   leaked=gold["forbidden"].casefold() in json.dumps(row).casefold())
    for row,target in zip(report["extraction"],gold["extract"],strict=True):
        row.update(target=target,correct="error" not in row and row["prediction"]==target)
    return report


if __name__ == "__main__":
    dest = Path(sys.argv[1])
    if dest.exists():
        raise SystemExit("Choose a new output path.")
    dest.write_text(json.dumps(score(run()),indent=2),encoding="utf-8")
