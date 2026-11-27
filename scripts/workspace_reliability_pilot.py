"""Frozen Workspace 40B raw-message acquisition and cross-chat answer pilot."""
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import sys

from trace_mem.workspace import server
from trace_mem.workspace_chat import PREFERRED
from trace_mem.workspace_reliability import extract_message

ROOT = Path(__file__).resolve().parents[1]/"research/workspace40b"


def run(inputs):
    extracts, answers = [], []
    with TemporaryDirectory() as tmp, server(Path(tmp)/"memory.json",0) as app:
        for index,(stamp,message) in enumerate(inputs["messages"]):
            started=perf_counter()
            claims,usage=extract_message(message,date.fromisoformat(stamp),app.opener,PREFERRED)
            saved=[]
            for c in claims:
                prior=next((r for r in reversed(app.store.rows) if r["key"]==c.predicate),None)
                if c.intent=="uncertain" or prior and (prior["value"]==c.value or c.intent!="correct"):
                    continue
                app.store.save(c.predicate,c.value,c.effective_on.isoformat(),
                               replaces=prior["id"] if prior else None,origin=f"fixture/{index}")
                saved.append([c.predicate,c.value,c.intent])
            extracts.append(dict(claims=[[c.predicate,c.value,c.intent] for c in claims],
                                 saved=saved,usage=usage,seconds=perf_counter()-started))
        modes=["standard","rag","trace"]
        for index,(stamp,question) in enumerate(inputs["queries"]):
            for mode in modes[index%3:]+modes[:index%3]:
                started=perf_counter()
                chat=app.chats.action("new",{})["chat"]
                chunks=[]
                row=dict(index=index,mode=mode)
                try:
                    result=app.chats.generate(dict(chat=chat,question=question,strategy=mode,output=48,
                        temperature=0,budget=512,model=PREFERRED),app.store,app.opener,
                        lambda r:chunks.append(r["text"]),date.fromisoformat(stamp))
                    row.update(answer="".join(chunks),evidence=[n["value"] for n in result["evidence"]],
                               prompt=result["prompt"],output=result["output"],reason=result["reader_reason"])
                except (ValueError,OSError,KeyError) as exc:
                    row["error"]=str(exc)
                row["seconds"]=perf_counter()-started
                answers.append(row)
                print(index,mode,row.get("answer",row.get("error")),flush=True)
    return dict(extracts=extracts,answers=answers)


def grade(report,key):
    for row,target in zip(report["extracts"],key["claims"],strict=True):
        predicted=set(map(tuple,row["claims"]))
        expected=set(map(tuple,target))
        row.update(tp=len(predicted&expected),fp=len(predicted-expected),fn=len(expected-predicted),
                   false_saves=len(set(map(tuple,row["saved"]))-expected))
    for row in report["answers"]:
        expected=key["answers"][row["index"]]
        actual=row.get("answer","").strip().rstrip(".!").casefold()
        row.update(correct=actual==expected.casefold(),supported=expected!="UNKNOWN" and expected in row.get("evidence",[]),
                   abstained=actual=="unknown")
    return report


if __name__=="__main__":
    path=Path(sys.argv[1])
    if path.exists():
        raise SystemExit("Choose a new output file")
    report=run(json.loads((ROOT/"inputs.json").read_text()))
    path.write_text(json.dumps(grade(report,json.loads((ROOT/"scoring.json").read_text())),indent=2),encoding="utf-8")
