"""Exact-request cache reuse and measured logical token accounting for Step 31."""

from contextlib import closing
import sqlite3

from trace_mem.providers import ChatProvider, LimitExceeded, ProviderError, http_transport


def legacy_usage(path):
    """Recover usage from the single-writer, retry-free, all-success Step 30 verifier."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        responses = db.execute("SELECT rowid, key FROM response ORDER BY rowid").fetchall()
        attempts = db.execute("SELECT id,status,input_tokens,output_tokens FROM attempt ORDER BY id").fetchall()
    if len(responses) != 814 or len(attempts) != len(responses):
        raise ValueError("Unexpected Step 30 verifier ledger length")
    usage = {}
    for index, ((rowid, key), (attempt, status, prompt, output)) in enumerate(
        zip(responses, attempts, strict=True), 1
    ):
        if rowid != index or attempt != index or status != "ok" or prompt is None or output is None:
            raise ValueError("Cannot recover legacy request usage from insertion order")
        usage[key] = (prompt, output)
    return usage


class MeasuredCache:
    def __init__(self, config, directory, name, legacy, *, tokens=False):
        self.config = config
        self.capture = None
        self.fatal = None
        self.current_usage = None
        self.path = directory / f"{name}-indexed.sqlite"
        self.provider = ChatProvider(config, directory / f"{name}.sqlite", transport=self.transport)
        with closing(sqlite3.connect(legacy.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            self.legacy = dict(db.execute("SELECT key,text FROM response"))
        self.legacy_tokens = legacy_usage(legacy) if tokens else {}
        self.reused = 0
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS result "
                       "(key TEXT PRIMARY KEY, text TEXT, error TEXT, prompt INTEGER, output INTEGER)")
            self.saved = {r[0]: r[1:] for r in db.execute("SELECT * FROM result")}

    def transport(self, url, headers, body, timeout):
        raw = http_transport(url, headers, body, timeout)
        self.capture = raw.get("prompt_eval_count"), raw.get("eval_count")
        return raw

    def generate(self, task, system, payload, validate):
        url, _, body = self.provider.request_for(self.config, task, system, payload)
        key = self.provider.cache_key(task, url, body)
        self.current_usage = None
        if key in self.legacy:
            text = self.legacy[key]
            self.provider._validate(text, validate)
            self.current_usage = self.legacy_tokens.get(key)
            self.reused += 1
            return text
        if key in self.saved:
            text, error, prompt, output = self.saved[key]
            self.current_usage = (prompt, output) if prompt is not None and output is not None else None
            if error:
                raise ProviderError(error)
            self.provider._validate(text, validate)
            self.reused += 1
            return text
        self.capture = None
        text = error = None
        try:
            text = self.provider.generate(task, system, payload, validate)
        except LimitExceeded as exc:
            self.fatal = exc
            raise
        except ProviderError as exc:
            if self.capture is None:
                self.fatal = exc
                raise
            error = str(exc)
        prompt, output = self.capture or (None, None)
        self.current_usage = (prompt, output) if prompt is not None and output is not None else None
        row = (text, error, prompt, output)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO result VALUES (?,?,?,?,?)", (key, *row))
        self.saved[key] = row
        if error:
            raise ProviderError(error)
        return text
