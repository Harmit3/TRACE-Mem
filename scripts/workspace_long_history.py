"""Six prefixes of a fictional trajectory with separately scored reader probes."""
from collections import Counter
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

from trace_mem.workspace import server
from trace_mem.workspace_encoder import LocalEncoder
from trace_mem.workspace_chat import PREFERRED
from trace_mem.workspace_reliability import extract_message

ROOT=Path(__file__).resolve().parents[1]/"research/workspace42"


def count(text):
    return len(re.findall(r"\w+|[^\w\s]",text))


def run(fixture):
    results=[]
    with TemporaryDirectory() as temp,server(Path(temp)/"memory.json",0) as app:
        enc=LocalEncoder()
        app.chats.encoder=enc
        try:
            store=app.store
            for key,value,start in fixture["facts"]:
                old=next((r for r in reversed(store.rows) if r["key"]==key),None)
                store.save(key,value,start,replaces=old["id"] if old else None,share=True,share_revisions=True)
            store.save("badge","JUNCO-383","2025-01-01")
            store.forget("badge")
            started=perf_counter()
            claim,usage=extract_message("I might move to Kite Hill.",date(2025,3,1),app.opener,PREFERRED)
            acquisition=dict(proposed=claim[0].intent,seconds=perf_counter()-started,usage=usage)
            for length in fixture["lengths"]:
                turns=[(fixture["initial"],"Recorded.")]
                size=count(" ".join(turns[0]))
                while size<length:
                    turn=(f"Exercise {len(turns)}. "+(fixture["distractor"]+" ")*4,"Finished.")
                    turns.append(turn)
                    size+=count(" ".join(turn))
                for ix,(kind,q,stamp) in enumerate(fixture["questions"]):
                    modes=["standard","rag","trace"]
                    for mode in modes[ix:]+modes[:ix]:
                        chat=app.chats.action("new",{})["chat"]
                        with closing(app.chats.connect()) as db,db:
                            db.executemany("INSERT INTO turns(chat,question,answer,model_context) VALUES(?,?,?,1)",
                                           [(chat,a,b) for a,b in turns])
                        started=perf_counter()
                        row=dict(length=length,estimated=size,turns=len(turns),mode=mode,kind=kind,
                                 memory_bytes=store.path.stat().st_size,chat_db_bytes=app.chats.path.stat().st_size)
                        parts=[]
                        try:
                            out=app.chats.generate(dict(chat=chat,model=PREFERRED,question=q,strategy=mode,semantic=True,
                                temperature=0,output=32,budget=1024,structured=False),store,app.opener,
                                lambda v:parts.append(v["text"]),date.fromisoformat(stamp))
                            row.update(answer="".join(parts),values=[n["value"] for n in out["evidence"]],
                                       prompt=out["prompt"],output=out["output"],admitted=out["history"],direct=bool(out["reader_reason"]))
                        except (OSError,ValueError,KeyError) as err:
                            row["error"]=str(err)
                        row["seconds"]=perf_counter()-started
                        results.append(row)
                        app.chats.action("remove",dict(chat=chat))
                print(length,"complete",flush=True)
            from trace_mem.workspace import Store
            probe=Store(Path(temp)/"paraphrase.json")
            for key,value in zip(["residence","job","education","project"],["Elm Quay","Acorn Works","Brook Hall","Tile Map"]):
                probe.save(key,value,"2025-01-01")
            paraphrases=[]
            for question,_ in fixture["paraphrases"]:
                def top(semantic):
                    rows=app.chats.retrieve(probe,question,date.today(),1024,"rag",semantic=semantic)
                    return rows[0]["label"] if rows else None
                paraphrases.append([top(False),top(True)])
            return dict(rows=results,paraphrases=paraphrases,semantic_available=app.chats.semantic_available,
                        acquisition=acquisition,deleted_absent=not any(r["key"]=="badge" for r in store.rows))
        finally:
            enc.close()


if __name__=="__main__":
    dest=Path(sys.argv[1])
    if dest.exists(): raise SystemExit("Choose a new output.")
    fixture=json.loads((ROOT/"inputs.json").read_text())
    out=run(fixture)
    gold=json.loads((ROOT/"score.json").read_text())
    for row in out["rows"]:
        i=["current","historic","reason"].index(row["kind"])
        row["correct"]=row.get("answer","").strip().casefold().rstrip(".!")==gold[i].casefold()
        required=[gold[i]] if i<2 else ["60","3"]
        row["hits"]=sum((Counter(required)&Counter(row.get("values",[]))).values())
        row["required"]=len(required)
    dest.write_text(json.dumps(out,indent=2),encoding="utf-8")
