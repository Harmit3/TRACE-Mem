"""Private desktop host. Closing the launcher pipe stops the loopback server."""
from contextlib import closing
import json
import msvcrt
from pathlib import Path
import sys
import threading

from trace_mem.workspace import server


def main(profile):
    profile.mkdir(parents=True,exist_ok=True)
    with (profile/"session.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        with server(profile/"memory.json",0,protect=True) as app:
            from trace_mem.workspace_encoder import LocalEncoder
            app.chats.encoder=LocalEncoder()
            with closing(app.chats.connect()) as db:
                if db.execute("PRAGMA quick_check").fetchone()!=("ok",):
                    raise ValueError("Chat archive integrity check failed")
            app.daemon_threads=False
            def monitor():
                sys.stdin.readline()
                app.shutdown()
            threading.Thread(target=monitor,daemon=True).start()
            print(json.dumps(app.server_port),flush=True)
            try:
                app.serve_forever(poll_interval=.15)
            finally:
                app.chats.encoder.close()


if __name__=="__main__":
    main(Path(sys.argv[1]))
