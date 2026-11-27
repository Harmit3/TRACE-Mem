"""Exercise a freshly extracted Windows package with a disposable fictional profile."""
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
import json
import socket
import sqlite3
import subprocess
import sys
import zipfile

from playwright.sync_api import expect, sync_playwright


@contextmanager
def host(folder,profile):
    proc=subprocess.Popen([str(folder/"runtime/python.exe"),"-B","-m","trace_mem.workspace_desktop",str(profile)],
        cwd=folder,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        port=proc.stdout.readline().strip()
        if not port:
            raise RuntimeError(proc.stderr.read())
        yield "http://127.0.0.1:"+port
    finally:
        proc.stdin.close()
        assert proc.wait(timeout=30)==0


def api(url,name,data):
    with urlopen(url+"/api/session") as response:
        token=json.load(response)["token"]
    req=Request(url+"/api/"+name,json.dumps(data).encode(),{"Content-Type":"application/json",
                "Origin":url,"X-Workspace-Token":token})
    with urlopen(req) as response:
        return json.load(response)


def smoke(package, semantic=False):
    with TemporaryDirectory() as tmp, sync_playwright() as pw:
        root=Path(tmp)
        profile=root/"profile"
        profile.mkdir()
        (profile/"memory.json").write_text("[]")
        with closing(sqlite3.connect(profile/"memory.chats.sqlite3")) as db, db:
            db.executescript("CREATE TABLE chats(id TEXT PRIMARY KEY,title TEXT NOT NULL); CREATE TABLE turns(id INTEGER PRIMARY KEY,chat TEXT REFERENCES chats(id) ON DELETE CASCADE,question TEXT,answer TEXT,permitted INTEGER DEFAULT 1); PRAGMA user_version=1;")
            db.execute("INSERT INTO chats VALUES('old','Prior title')")
            db.execute("INSERT INTO turns(chat,question,answer) VALUES('old','Sensitive migration fixture','Fictional reply')")
        browser=pw.chromium.launch(channel="msedge")
        page=browser.new_page()
        for part in ("initial","upgrade"):
            folder=root/part
            with zipfile.ZipFile(package) as archive:
                assert archive.testzip() is None
                archive.extractall(folder)
            with host(folder,profile) as url:
                if part=="initial":
                    page.goto(url)
                    expect(page.locator("#mode")).to_have_value("ollama")
                    page.locator("#new").click()
                    page.locator("#question").fill("I live in fictional Fawn Bay.")
                    page.locator("#send").click()
                    review=page.get_by_role("button",name="Review assert")
                    review.wait_for(timeout=90000)
                    page.on("dialog",lambda d:d.accept(d.default_value))
                    review.click()
                    expect(page.locator("#count")).to_have_text("1")
                    api(url,"save",dict(key="office",value="Owl Hall",date="2025-01-01"))
                    fact=next(x for x in api(url,"list",dict(date="2025-01-01"))["facts"] if x["key"]=="office")
                    api(url,"save",dict(key="office",value="Pine Hall",date="2025-02-01",replaces=fact["id"]))
                    if semantic:
                        page.locator("details").filter(has=page.locator("#semantic")).first.locator("summary").first.click()
                        page.locator("#semantic").check()
                        page.locator("#question").fill("Which geographic area is associated with these notes?")
                        page.locator("#send").click()
                        expect(page.locator("#retrieved")).to_contain_text("local encoder ready",timeout=120000)
                    old_port=int(url.rsplit(":",1)[1])
                else:
                    assert int(url.rsplit(":",1)[1])!=old_port
                    page.goto(url)
                    expect(page.locator("#chats option")).to_have_count(2)
                    q=dict(question="office",mode="memory",date="2025-01-15",budget=512)
                    assert "Owl Hall" in api(url,"ask",q)["answer"]
                    api(url,"forget",dict(key="office"))
                    assert not api(url,"ask",q)["evidence"]
                    assert "Pine Hall".encode() not in (profile/"memory.json").read_bytes()
                    assert api(url,"chats/history",dict(chat="old"))["turns"]==[["Sensitive migration fixture","Fictional reply"]]
                    assert b"Sensitive migration fixture" not in (profile/"memory.chats.sqlite3").read_bytes()
                    page.locator("#longHistory summary").click()
                    expect(page.locator("#historyResults tr")).to_have_count(7)
                    page.locator("#practice summary").click()
                    page.locator("#persona").select_option(index=1)
                    expect(page.locator("#story")).to_contain_text("Copper Hill")
                    page.locator("#pilot summary").click()
                    expect(page.locator("#pilotReport table tr")).to_have_count(4)
            if part=="initial":
                busy=socket.socket()
                busy.bind(("127.0.0.1",old_port))
                busy.listen()
        busy.close()
        browser.close()
        assert (profile/"memory.json").read_bytes().startswith(b"TMDP1")
        with closing(sqlite3.connect(profile/"memory.chats.sqlite3")) as db, db:
            assert db.execute("PRAGMA integrity_check").fetchone()==("ok",)
            assert db.execute("PRAGMA user_version").fetchone()==(3,)
        print("Package CRC, clean extraction, migration, live browser confirmation, persistence, upgrade, port contention, offline historical lookup, deletion, DPAPI, dashboard and orderly shutdown passed.")


if __name__=="__main__":
    smoke(Path(sys.argv[1]).resolve(), "--semantic" in sys.argv[2:])
