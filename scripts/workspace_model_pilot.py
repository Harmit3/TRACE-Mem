"""Matched fictional model pilot for the portable Windows beta."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import json
import sys

import psutil
from trace_mem.workspace import server
from trace_mem.workspace_reliability import extract_message

ROOT=Path(__file__).resolve().parents[1]/"research/workspace41"


def resources(app):
    with app.opener.open("http://127.0.0.1:11434/api/ps",timeout=5) as response:
        models=json.load(response)["models"]
    return dict(models=[{k:m.get(k) for k in ("name","size","size_vram")} for m in models],
                system_used=psutil.virtual_memory().used)


def run(model,fixture):
    rows=[]
    with TemporaryDirectory() as tmp, server(Path(tmp)/"memory.json",0) as app:
        app.chats.semantic_available=False
        for key,value,start in fixture["notes"]:
            existing=[r for r in app.store.rows if r["key"]==key]
            app.store.save(key,value,start,key.startswith("workshop") or key=="duration minutes",
                           replaces=existing[-1]["id"] if existing else None,share=key=="duration minutes")
        initial=resources(app)
        for i,text in enumerate(fixture["extract"]):
            start=perf_counter()
            claims,usage=extract_message(text,date(2025,4,1),app.opener,model)
            rows.append(dict(task="extract",i=i,claims=[[c.predicate,c.value,c.intent] for c in claims],
                             usage=usage,seconds=perf_counter()-start,resources=resources(app)))
        for trial in range(2):
            for task,question in fixture["questions"]:
                chat=app.chats.action("new",{})["chat"]
                start=perf_counter()
                chunks=[]
                row=dict(task=task,trial=trial)
                try:
                    result=app.chats.generate(dict(chat=chat,model=model,strategy="trace",question=question,
                        temperature=0,output=48,budget=1024,structured=False),app.store,app.opener,
                        lambda r:chunks.append(r["text"]),date(2025,1,15) if task=="history" else date(2025,4,1))
                    row.update(answer="".join(chunks),direct=bool(result["reader_reason"]),prompt=result["prompt"],
                               output=result["output"],evidence=[n["value"] for n in result["evidence"]])
                except (ValueError,OSError,KeyError) as exc:
                    row["error"]=type(exc).__name__
                row.update(seconds=perf_counter()-start,resources=resources(app))
                rows.append(row)
        return dict(initial=initial,rows=rows)


if __name__=="__main__":
    dest=Path(sys.argv[1])
    if dest.exists():
        raise SystemExit("Choose a new result file.")
    fixture=json.loads((ROOT/"inputs.json").read_text())
    result={name:run(name,fixture) for name in ("qwen2.5:7b-instruct-q4_K_M","llama3.2:3b")}
    key=json.loads((ROOT/"score.json").read_text())
    targets=dict(zip([q[0] for q in fixture["questions"]],key["answers"]))
    for data in result.values():
        for r in data["rows"]:
            if r["task"]=="extract":
                a,b=set(map(tuple,r["claims"])),set(map(tuple,key["extract"][r["i"]]))
                r.update(tp=len(a&b),fp=len(a-b),fn=len(b-a))
            elif r["task"] in targets:
                r["correct"]=r.get("answer","").lower().strip().rstrip(".!")==targets[r["task"]].lower()
            else:
                r["marker"]= "ORCHID-599" in json.dumps([r.get("answer"),r.get("evidence")])
    dest.write_text(json.dumps(result,indent=2),encoding="utf-8")
