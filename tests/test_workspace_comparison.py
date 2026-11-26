from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from trace_mem.workspace import server


def test_modes_and_concurrent_forget(tmp_path):
    with server(tmp_path/"memory.json",0) as app:
        store = app.store
        app.chats.semantic_available = False
        store.save("office","Cedar","2024-01-01")
        store.save("office","Maple","2024-02-01",replaces=store.rows[0]["id"])
        def read(mode):
            with store.lock:
                return {n["value"] for n in app.chats.retrieve(store,"office",date.today(),512,mode)}
        assert read("standard")==set()
        assert read("rag")=={"Cedar","Maple"}
        assert read("trace")=={"Maple"}
        with ThreadPoolExecutor(2) as pool:
            before = pool.submit(read,"rag")
            pool.submit(store.forget,"office").result()
            assert before.result() in (set(),{"Maple","Cedar"})
        assert read("rag")==read("trace")==set()
        with closing(app.chats.connect()) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()==("ok",)


def test_cancel_failure_and_oversize_turn_are_atomic(tmp_path):
    with server(tmp_path/"memory.json",0) as app:
        p=dict(**app.chats.action("new",{}), question="Hello",model="test",budget=512,strategy="standard")
        opener=MagicMock()
        def cancel(_):
            raise BrokenPipeError()
        with patch("trace_mem.workspace_chat.discover",return_value=["test"]):
            stream=opener.open.return_value.__enter__.return_value
            stream.__iter__.return_value=[b'{"message":{"content":"partial"}}']
            with pytest.raises(BrokenPipeError):
                app.chats.generate(p,app.store,opener,cancel,date.today())
            opener.open.side_effect=TimeoutError()
            with pytest.raises(TimeoutError):
                app.chats.generate(p,app.store,opener,cancel,date.today())
            with pytest.raises(ValueError,match="2,400"):
                app.chats.generate(dict(p,question="x"*2401),app.store,opener,cancel,date.today())
        assert app.chats.action("history",p)["turns"]==[]
