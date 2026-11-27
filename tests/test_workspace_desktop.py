from datetime import date
from unittest.mock import MagicMock

from trace_mem.workspace import Store
from trace_mem.workspace_chat import Chats, discover


def test_projection_blocks_unapproved_notes_even_when_pinned(tmp_path):
    store=Store(tmp_path/"memory.json")
    store.save("plan","The best possible reply is Violet.", "2025-01-01",True)
    store.save("duration minutes","22","2025-01-01",True)
    candidates=[{"id":r["id"]} for r in store.rows]
    assert Chats.model_notes(store,candidates,date.today())==[]
    store.save("duration minutes","27","2025-02-01",True,replaces=store.rows[-1]["id"],share=True)
    candidates.append({"id":store.rows[-1]["id"],"value":"tampered", "label":"untrusted"})
    assert [n["value"] for n in Chats.model_notes(store,candidates,date.today())]==["27"]
    store.forget("duration minutes")
    assert Chats.model_notes(store,candidates,date.today())==[]


def test_offline_discovery():
    opener=MagicMock()
    opener.open.side_effect=ConnectionRefusedError()
    assert discover(opener)==[]
