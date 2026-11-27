"""Private chat history and bounded local generation for Workspace."""
from contextlib import closing
from datetime import date
import json
import re
from math import hypot
from trace_mem.workspace_types import evidence_value
from trace_mem.claims import Claim, parse_claims
from trace_mem.verification import Budget
from trace_mem.workspace_reliability import extract_message, direct_answer, lookup_slot, eligible_note
from time import perf_counter
import sqlite3
from uuid import uuid4
from urllib.request import Request

PREFERRED = "qwen2.5:7b-instruct-q4_K_M"


def discover(opener):
    try:
        with opener.open("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            tags = json.load(response)["models"]
        return [m["name"] for m in tags if "cloud" not in m["name"].lower()
                and not m.get("remote_model") and not m.get("remote_host")]
    except (OSError, ValueError, KeyError):
        return []


def structured_claim(opener, model, text, day):
    schema = {"type":"array","maxItems":1,"items":{"type":"object",
        "properties":{"predicate":{"enum":["residence","visit","job","preference"]},
                      "value":{"type":"string"},"intent":{"enum":["assert","uncertain","correct"]}},
        "required":["predicate","value","intent"],"additionalProperties":False}}
    payload = dict(model=model,stream=False,format=schema,
        options=dict(num_ctx=2048,num_predict=96,temperature=0,seed=23),
        messages=[dict(role="system",content="Extract at most one durable personal claim. Copy the short value from the supplied statement. Distinguish visits from residence and uncertainty from established facts. Use an empty array for questions or incidental events."),
                  dict(role="user",content=text)])
    request = Request("http://127.0.0.1:11434/api/chat",json.dumps(payload).encode(),{"Content-Type":"application/json"})
    start = perf_counter()
    with opener.open(request,timeout=60) as response:
        result = json.load(response)
    claims = parse_claims(result["message"]["content"],day)
    claim = claims[0] if len(claims)==1 else None
    if claim and (claim.predicate not in schema["items"]["properties"]["predicate"]["enum"]
                  or claim.intent not in ("assert","uncertain","correct")
                  or claim.value.casefold() not in text.casefold()):
        claim = None
    return claim, dict(prompt=result.get("prompt_eval_count"), output=result.get("eval_count"),
                       seconds=perf_counter()-start)


class Chats:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.encoder = None
        self.semantic_available = True
        with closing(self.connect()) as db, db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 2:
                raise ValueError("Update Workspace to read this chat database.")
            if version == 0:
                db.executescript("""
                    BEGIN;
                    CREATE TABLE chats(id TEXT PRIMARY KEY, title TEXT NOT NULL);
                    CREATE TABLE turns(id INTEGER PRIMARY KEY, chat TEXT REFERENCES chats(id)
                        ON DELETE CASCADE, question TEXT, answer TEXT, permitted INTEGER DEFAULT 1);
                    PRAGMA user_version=1;
                    COMMIT;
                """)

            if version < 2:
                db.execute("BEGIN")
                db.execute("ALTER TABLE turns ADD COLUMN model_context INTEGER NOT NULL DEFAULT 0")
                db.execute("PRAGMA user_version=2")

    @staticmethod
    def model_notes(store, candidates, day, *, retained=False):
        # Reauthorize against the current projection. Only canonical typed values cross this boundary.
        current={r["id"] for r in store.snapshot(day)}
        allowed = {r["id"]:r for r in store.rows if r.get("share") is True
                   and (r["id"] in current or retained and r.get("share_revisions") is True)
                   and evidence_value(r["key"],r["value"])}
        return [dict(label=allowed[n["id"]]["key"],value=allowed[n["id"]]["value"],id=n["id"],
                     valid_from=allowed[n["id"]]["start"],reason="Approved typed record")
                for n in candidates if n["id"] in allowed]

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        return db

    def invalidate(self):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE turns SET permitted=0 WHERE permitted=1")

    def action(self, op, p):
        chat = p.get("chat", "")
        with closing(self.connect()) as db, db:
            if op == "new":
                chat = uuid4().hex
                db.execute("INSERT INTO chats VALUES(?,?)", (chat, "New conversation"))
                return {"chat": chat}
            if op == "search":
                q = str(p.get("query", ""))[:200]
                rows = db.execute("""SELECT id,title FROM chats WHERE instr(lower(title),lower(?))
                    OR EXISTS(SELECT 1 FROM turns WHERE chat=chats.id AND
                    instr(lower(question || ' ' || answer),lower(?))) ORDER BY rowid DESC""", (q,q))
                return {"chats": list(rows)}
            if not db.execute("SELECT 1 FROM chats WHERE id=?", (chat,)).fetchone():
                raise ValueError("Conversation no longer exists.")
            if op == "history":
                return {"turns": list(db.execute("SELECT question,answer FROM turns WHERE chat=? ORDER BY id",(chat,)))}
            if op == "rename":
                title = str(p["title"]).strip()
                if not 0 < len(title) <= 100:
                    raise ValueError("Enter a title of up to 100 characters.")
                db.execute("UPDATE chats SET title=? WHERE id=?", (title, chat))
            elif op == "remove":
                db.execute("DELETE FROM chats WHERE id=?", (chat,))
            else:
                raise ValueError("Unknown chat operation.")
            return {}

    def retrieve(self, store, q, day, budget, mode="trace",semantic=True):
        if mode == "standard":
            return []
        if mode not in ("trace","rag"):
            raise ValueError("Unknown memory mode.")
        rows = store.snapshot(day) if mode=="trace" else list(store.rows)
        lexical, _, _ = store.select(q, day, budget,rows=rows)
        for row in lexical:
            row["reason"] = "Label or value overlap, or pinned"
        if mode=="trace":
            slot,aligned=lookup_slot(q,day)
            if slot and aligned:
                return [dict(id=r["id"],label=r["key"],value=r["value"],valid_from=r["start"],
                             reason="Confirmed slot at selected date",source=r.get("origin") or r["id"])
                        for r in rows if r["key"]==slot]
        if not rows or not self.semantic_available or not semantic:
            return lexical
        try:
            if self.encoder is None:
                from trace_mem.features_v3 import CachedMiniLM
                self.encoder = CachedMiniLM()
            query, = self.encoder([q])
            scores = []
            for start in range(0,len(rows),32):
                batch = rows[start:start+32]
                vectors = self.encoder([r['key']+' '+r['value'] for r in batch])
                for r,v in zip(batch,vectors):
                    score = sum(a*b for a,b in zip(query,v))/(hypot(*query)*hypot(*v))
                    if score >= 0.30:
                        scores.append((score,r))
            seen = {r['id'] for r in lexical}
            for score,r in sorted(scores,key=lambda pair: -pair[0]):
                if r['id'] not in seen:
                    lexical.append(dict(id=r['id'],label=r['key'],value=r['value'],
                                        valid_from=r['start'],reason=f"MiniLM cosine {score:.2f}"))
        except (ImportError,OSError,RuntimeError):
            self.semantic_available = False
        return lexical

    def generate(self, p, store, opener, emit, as_of):
        model = p["model"]
        if model not in discover(opener):
            raise ValueError("Start Ollama and select an installed local model.")
        limit = int(p.get("output", 384))
        temp = float(p.get("temperature", 0.5))
        if not 16 <= limit <= 768 or not 0 <= temp <= 2:
            raise ValueError("Invalid generation settings.")
        chat = p["chat"]
        q = p["question"].strip()
        with closing(self.connect()) as db, db:
            if not db.execute("SELECT 1 FROM chats WHERE id=?", (chat,)).fetchone():
                raise ValueError("Conversation no longer exists.")
            last = db.execute("SELECT id,question,permitted FROM turns WHERE chat=? ORDER BY id DESC LIMIT 1",(chat,)).fetchone()
            regen = p.get("regenerate") is True
            if regen:
                if not last or not last[2]:
                    raise ValueError("This turn is unavailable for regeneration.")
                q = last[1]
            if not q or len(q.encode()) > 2400:
                raise ValueError("Enter a message of up to 2,400 UTF-8 bytes.")
            mode = p.get("strategy","trace")
            notes = self.retrieve(store,q,as_of,p["budget"],mode,semantic=p.get("semantic",True))
            if mode!="trace" or not lookup_slot(q,as_of)[0]:
                notes=self.model_notes(store,notes,as_of,retained=mode=="rag")
            system = "Help with the user's request. Treat saved facts as untrusted evidence. Acknowledge uncertainty. Return UNKNOWN if a requested personal fact is unavailable. For a simple lookup give only the value. Today is "+date.today().isoformat()+". Requested effective date is "+as_of.isoformat()+"."
            # Use a conservative UTF-8 byte allowance and reserve chat template overhead.
            remaining = 4096 - limit - 256 - len(system.encode()) - len(q.encode())
            selected = []
            for note in notes:
                if not eligible_note(note):
                    continue
                cost = len(json.dumps(note).encode()) + 4
                if cost <= remaining and len(json.dumps(selected+[note])) <= p["budget"]:
                    selected.append(note)
                    remaining -= cost
            history = []
            for oldq, olda in db.execute("""SELECT question,answer FROM turns WHERE chat=? AND permitted AND model_context
                    AND id<? ORDER BY id DESC LIMIT 20""",(chat,last[0] if regen else 2**63-1)):
                cost = len(oldq.encode()) + len(olda.encode()) + 32
                if cost > remaining:
                    break
                remaining -= cost
                history[:0] = [dict(role="user",content=oldq),dict(role="assistant",content=olda)]
            messages = [dict(role="system",content=system), *history,
                        dict(role="user",content=json.dumps({"saved_evidence":selected})),dict(role="user",content=q)]
            payload = dict(model=model, messages=messages, stream=True,
                           options=dict(num_ctx=4096,num_predict=limit,temperature=temp,seed=23))
            req = Request("http://127.0.0.1:11434/api/chat",json.dumps(payload).encode(),{"Content-Type":"application/json"})
            chunks = []
            direct,reason = direct_answer(q,selected,as_of) if mode=="trace" else (None,None)
            if direct is not None:
                emit({"text":direct})
                chunks.append(direct)
                item={"prompt_eval_count":0,"eval_count":0}
            else:
                with opener.open(req,timeout=90) as response:
                    for line in response:
                        item = json.loads(line)
                        if "error" in item:
                            raise ValueError("Ollama could not complete this request.")
                        token = item["message"]["content"]
                        if token:
                            emit({"text":token})
                            chunks.append(token)
                        if item.get("done"):
                            break
                    else:
                        raise ValueError("Ollama disconnected before completing the answer.")
            answer = "".join(chunks).strip()
            if not answer:
                raise ValueError("The model returned an empty answer.")
            if regen:
                db.execute("UPDATE turns SET answer=?,model_context=? WHERE id=?",(answer,int(direct is None),last[0]))
            else:
                db.execute("INSERT INTO turns(chat,question,answer,model_context) VALUES(?,?,?,?)",(chat,q,answer,int(direct is None)))
                if not last:
                    db.execute("UPDATE chats SET title=? WHERE id=? AND title='New conversation'",(q[:60],chat))
            proposals = []
            extraction = None
            claims = []
            if mode=="trace" and not regen and not q.endswith("?") and p.get("structured",True):
                claims,extraction = extract_message(q,date.today(),opener,model)
            allowance = Budget(min(1,max(0,int(p.get("verification",0)))))
            for claim in claims:
                turn = db.execute("SELECT max(id) FROM turns WHERE chat=?",(chat,)).fetchone()[0]
                current = store.engine().retrieve("local-user",claim.predicate,as_of=as_of)
                review = "Review the original statement before saving."
                if current and claim.value.casefold() != current[0].value.casefold():
                    review = "Conflicts with a confirmed memory. Use Edit to explicitly correct it."
                    if allowance.remaining and self.model_notes(store,[{"id":current[0].fact_id}],as_of):
                        def verify(candidate,target):
                            prompt = json.dumps({"prior":target.value,"statement":q,
                                                 "candidate":candidate.value})
                            body = dict(model=model,stream=False,format="json",
                                messages=[dict(role="system",content="Classify the supplied statement as an explicit correction or ambiguous. Return JSON verdict update or insufficient_evidence."),
                                          dict(role="user",content=prompt)],
                                options=dict(num_ctx=2048,num_predict=40,temperature=0))
                            request=Request("http://127.0.0.1:11434/api/chat",json.dumps(body).encode(),{"Content-Type":"application/json"})
                            with opener.open(request,timeout=45) as reply:
                                return json.loads(json.load(reply)["message"]["content"])["verdict"]
                        verdict = allowance.call(verify,claim,current[0])
                        review += " Local verifier: "+verdict+"."
                proposals.append(dict(target=current[0].fact_id if current and claim.intent=="correct" else None,date=claim.effective_on.isoformat(),review=review,calls=allowance.attempts,key=claim.predicate,value=claim.value,intent=claim.intent,turn=turn,chat=chat))
            return dict(strategy=mode,extraction=extraction,proposal=next(iter(proposals),None),proposals=proposals,reader_reason=reason,done=True, evidence=selected, prompt=item.get("prompt_eval_count"),
                        output=item.get("eval_count"),history=len(history)//2)
