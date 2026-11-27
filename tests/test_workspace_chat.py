from contextlib import closing
from trace_mem.workspace_chat import Chats


def test_chat_lifecycle_and_privacy(tmp_path):
    path = tmp_path / "chats.sqlite3"
    chats = Chats(path)
    chat = chats.action("new", {})["chat"]
    chats.action("rename",dict(chat=chat,title="Study plan"))
    with closing(chats.connect()) as db, db:
        db.execute("INSERT INTO turns(chat,question,answer) VALUES(?,?,?)",(chat,"fictional note","Cedar"))
    assert Chats(path).action("search",dict(query="cedar"))["chats"] == [(chat,"Study plan")]
    chats.invalidate()
    with closing(chats.connect()) as db:
        assert db.execute("SELECT permitted FROM turns").fetchone() == (0,)
    chats.action("remove",dict(chat=chat))
    assert chats.action("search",{}) == {"chats":[]}
    with closing(chats.connect()) as db:
        assert db.execute("SELECT count(*) FROM turns").fetchone() == (0,)
