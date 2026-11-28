"""Optional CPU MiniLM worker. JSON pipes stay local and close with their parent."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from queue import Queue, Empty


class LocalEncoder:
    def __init__(self):
        self.proc = None

    def __call__(self,texts):
        if self.proc is None:
            python = Path(os.environ["ProgramFiles"])/"Python314/python.exe"
            self.proc = subprocess.Popen([str(python),"-E","-P","-B",str(Path(__file__).resolve()),"--worker"],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,
                encoding="utf-8",creationflags=subprocess.CREATE_NO_WINDOW)
            self.replies = Queue()
            out,queue=self.proc.stdout,self.replies
            def read():
                for line in out:
                    queue.put(line)
                queue.put("")
            threading.Thread(target=read,daemon=True).start()
        try:
            self.proc.stdin.write(json.dumps(texts)+"\n")
            self.proc.stdin.flush()
            line=self.replies.get(timeout=60)
            if not line:
                raise RuntimeError("Optional MiniLM installation unavailable")
            return json.loads(line)
        except (Empty,OSError,ValueError) as exc:
            self.close()
            raise RuntimeError("Optional local encoder unavailable") from exc

    def close(self):
        if self.proc:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.proc=None


if __name__=="__main__":
    import torch
    from transformers import AutoModel, AutoTokenizer
    torch.set_num_threads(2)
    kwargs=dict(revision="c9745ed1d9f207416be6d2e6f8de32d1f16199bf",local_files_only=True)
    name="sentence-transformers/all-MiniLM-L6-v2"
    tok=AutoTokenizer.from_pretrained(name,**kwargs)
    model=AutoModel.from_pretrained(name,use_safetensors=True,**kwargs).eval()
    for line in sys.stdin:
        with torch.inference_mode():
            batch=tok(json.loads(line),padding=True,truncation=True,max_length=128,return_tensors="pt")
            mask=batch.attention_mask.unsqueeze(-1)
            vec=(model(**batch).last_hidden_state*mask).sum(1)/mask.sum(1)
            print(json.dumps(vec.tolist()),flush=True)
