"""Budgeted, resumable JSON chat over OpenAI, OpenRouter, and local Ollama."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
import hashlib
from http.client import HTTPException
import json
import math
from pathlib import Path
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from trace_mem.llm_tasks import RESPONSE_SCHEMAS


class ProviderError(RuntimeError):
    """Provider failure with no request text, credentials, or response body."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class LimitExceeded(ProviderError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_transport(url: str, headers: dict, body: dict, timeout: float) -> dict:
    request = Request(url, json.dumps(body).encode(), headers, method="POST")
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(2_000_001)
    except HTTPError as error:
        status = error.code
        error.close()
        raise ProviderError(f"Provider HTTP {status}",
                            retryable=status in (408, 429, 500, 502, 503, 504)) from None
    except (URLError, OSError, HTTPException):
        raise ProviderError("Provider connection or timeout failure", retryable=True) from None
    if len(raw) > 2_000_000:
        raise ProviderError("Provider response exceeded size limit")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise ProviderError("Provider returned invalid JSON") from None


Transport = Callable[[str, dict, dict, float], dict]


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    backend: str
    model: str
    max_requests: int
    timeout: float = 30
    retries: int = 0
    max_input_tokens: int = 4096
    max_output_tokens: int = 256
    context_tokens: int | None = None
    seed: int = 0
    ollama_url: str = "http://127.0.0.1:11434"
    api_key: str | None = field(default=None, repr=False)
    allow_paid: bool = False
    max_spend: Decimal = Decimal(0)
    input_price: Decimal = Decimal(0)
    output_price: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if self.backend not in {"openai", "openrouter", "ollama"} or not self.model.strip():
            raise ValueError("Expected a supported provider and explicit model")
        for number in (self.max_requests, self.retries, self.max_input_tokens,
                       self.max_output_tokens, self.seed):
            if type(number) is not int or number < 0:
                raise ValueError("Request, retry, token and seed settings must be nonnegative integers")
        if not self.max_input_tokens or not self.max_output_tokens:
            raise ValueError("Token ceilings must be positive")
        if self.context_tokens is not None and (
            self.backend != "ollama" or type(self.context_tokens) is not int
            or self.context_tokens <= self.max_output_tokens
        ):
            raise ValueError("Local context must exceed the output token cap")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("Timeout must be finite and positive")
        for money in (self.max_spend, self.input_price, self.output_price):
            if not isinstance(money, Decimal) or not money.is_finite() or not 0 <= money <= 1_000_000:
                raise ValueError("Use finite nonnegative USD Decimal amounts")
        if self.backend == "ollama":
            url = urlsplit(self.ollama_url)
            if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or url.username is not None or url.path not in ("", "/")
                    or url.query or url.fragment):
                raise ValueError("Ollama must use a loopback HTTP origin")
            if self.model.casefold().endswith(":cloud") or "-cloud" in self.model.casefold():
                raise ValueError("Use a locally installed Ollama model")
        elif not (self.allow_paid and self.api_key and self.max_spend > 0
                  and self.input_price > 0 and self.output_price > 0):
            raise ValueError("Remote providers require explicit paid approval, credentials, prices and a cap")

    def price(self, input_tokens: int, output_tokens: int) -> int:
        """Compute USD nanodollars using configured rates per million tokens."""
        if self.backend == "ollama":
            return 0
        return int(((input_tokens * self.input_price + output_tokens * self.output_price)
                    * 1000).to_integral_value(rounding=ROUND_CEILING))


class ChatProvider:
    """One run ledger and content-addressed response cache in an ignored SQLite file."""

    def __init__(self, config: ProviderConfig, database: Path, *,
                 transport: Transport = http_transport, sleep: Callable[[float], None] = time.sleep):
        self.config = config
        self.database = database
        self.transport = transport
        self.sleep = sleep
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS response (key TEXT PRIMARY KEY, text TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempt (
                    id INTEGER PRIMARY KEY, cost INTEGER NOT NULL, status TEXT NOT NULL,
                    input_tokens INTEGER, output_tokens INTEGER, latency_ms REAL, model TEXT,
                    overrun INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS cache_hit (id INTEGER PRIMARY KEY);
            """)

    def _connect(self):
        return sqlite3.connect(self.database, timeout=15)

    def stats(self) -> dict:
        with closing(self._connect()) as db:
            calls, cost, input_count, output_count, elapsed = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(cost),0), COALESCE(SUM(input_tokens),0), "
                "COALESCE(SUM(output_tokens),0), COALESCE(SUM(latency_ms),0) FROM attempt"
            ).fetchone()
            statuses = dict(db.execute("SELECT status, COUNT(*) FROM attempt GROUP BY status"))
            hits, = db.execute("SELECT COUNT(*) FROM cache_hit").fetchone()
            models = [row[0] for row in db.execute(
                "SELECT DISTINCT model FROM attempt WHERE model IS NOT NULL ORDER BY model")]
        return dict(attempts=calls, cost_usd=str(Decimal(cost) / Decimal(10**9)),
                    input_tokens=input_count, output_tokens=output_count, latency_ms=elapsed,
                    statuses=statuses, cache_hits=hits, models=models)

    def _reserve(self) -> int:
        settings = self.config
        reserve = settings.price(settings.max_input_tokens, settings.max_output_tokens)
        cap = int(settings.max_spend * 10**9)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            count, spent, overrun = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(cost),0), COALESCE(MAX(overrun),0) FROM attempt"
            ).fetchone()
            if count >= settings.max_requests:
                raise LimitExceeded("Request limit reached")
            if overrun or spent + reserve > cap:
                raise LimitExceeded("Spending limit or billing ceiling reached")
            return db.execute("INSERT INTO attempt(cost,status) VALUES(?, 'reserved')",
                              (reserve,)).lastrowid

    @staticmethod
    def request_for(settings: ProviderConfig, task: str, system: str, payload: str) -> tuple[str, dict, dict]:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": payload}]
        headers = {"Content-Type": "application/json"}
        body = {"model": settings.model, "messages": messages, "stream": False}
        if settings.backend == "ollama":
            body["options"] = {"temperature": 0, "seed": settings.seed,
                               "num_predict": settings.max_output_tokens}
            if settings.context_tokens is not None:
                body["options"]["num_ctx"] = settings.context_tokens
            if task in RESPONSE_SCHEMAS:
                body["format"] = RESPONSE_SCHEMAS[task]
            return settings.ollama_url.rstrip("/") + "/api/chat", headers, body
        headers["Authorization"] = f"Bearer {settings.api_key}"
        if settings.backend == "openai":
            body.update(max_completion_tokens=settings.max_output_tokens, store=False)
            return "https://api.openai.com/v1/chat/completions", headers, body
        body.update(max_tokens=settings.max_output_tokens, temperature=0, seed=settings.seed,
                    provider={"allow_fallbacks": False, "require_parameters": True,
                              "data_collection": "deny",
                              "max_price": {"prompt": float(settings.input_price),
                                            "completion": float(settings.output_price), "request": 0}})
        return "https://openrouter.ai/api/v1/chat/completions", headers, body

    def _request(self, task: str, system: str, payload: str) -> tuple[str, dict, dict]:
        return self.request_for(self.config, task, system, payload)

    @staticmethod
    def cache_key(task: str, url: str, body: dict) -> str:
        return hashlib.sha256(json.dumps([task, url, body], sort_keys=True).encode()).hexdigest()

    def _response(self, raw: dict) -> tuple[str, int, int, str, bool]:
        try:
            model = raw.get("model", self.config.model)
            if self.config.backend == "ollama":
                text = raw["message"]["content"]
                input_count, output_count = raw["prompt_eval_count"], raw["eval_count"]
                finished = raw["done"] is True and raw.get("done_reason") in ("stop", None)
            else:
                choice = raw["choices"][0]
                text = choice["message"]["content"]
                finished = choice["finish_reason"] == "stop" and not choice["message"].get("refusal")
                usage = raw["usage"]
                input_count, output_count = usage["prompt_tokens"], usage["completion_tokens"]
            if (not isinstance(text, str) or not isinstance(model, str)
                    or any(type(n) is not int or n < 0 for n in (input_count, output_count))):
                raise ValueError
        except (AttributeError, KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("Provider response lacked content or valid token usage") from None
        return text, input_count, output_count, model, finished

    def generate(self, task: str, system: str, payload: str, validate: Callable[[str], None]) -> str:
        url, headers, body = self._request(task, system, payload)
        key = self.cache_key(task, url, body)
        with closing(self._connect()) as db, db:
            cached = db.execute("SELECT text FROM response WHERE key=?", (key,)).fetchone()
            if cached:
                self._validate(cached[0], validate)
                db.execute("INSERT INTO cache_hit DEFAULT VALUES")
                return cached[0]
        input_ceiling = self.config.max_input_tokens
        if self.config.context_tokens is not None:
            input_ceiling = min(input_ceiling, self.config.context_tokens - self.config.max_output_tokens)
        if len((system + payload).encode()) + 128 > input_ceiling:
            raise LimitExceeded("Input exceeds conservative preflight ceiling")
        for retry in range(self.config.retries + 1):
            attempt = self._reserve()
            started = time.perf_counter()
            try:
                raw = self.transport(url, headers, body, self.config.timeout)
                text, input_count, output_count, model, finished = self._response(raw)
            except ProviderError as error:
                with closing(self._connect()) as db, db:
                    db.execute("UPDATE attempt SET status='unknown', latency_ms=? WHERE id=?",
                               ((time.perf_counter() - started) * 1000, attempt))
                if not error.retryable or retry == self.config.retries:
                    raise
                self.sleep(min(2**retry, 8))
                continue
            elapsed = (time.perf_counter() - started) * 1000
            overrun = (input_count > input_ceiling
                       or output_count > self.config.max_output_tokens)
            failure = None
            try:
                if overrun:
                    raise LimitExceeded("Provider usage exceeded a configured token ceiling")
                if not finished:
                    raise ProviderError("Provider response was incomplete or refused")
                self._validate(text, validate)
            except ProviderError as error:
                failure = error
            with closing(self._connect()) as db, db:
                db.execute(
                    "UPDATE attempt SET cost=?, status=?, input_tokens=?, output_tokens=?, latency_ms=?, "
                    "model=?, overrun=? WHERE id=?",
                    (self.config.price(input_count, output_count), "invalid" if failure else "ok",
                     input_count, output_count, elapsed, model, int(overrun), attempt),
                )
                if failure is None:
                    db.execute("INSERT OR IGNORE INTO response VALUES (?,?)", (key, text))
            if failure is not None:
                raise failure
            return text
        raise AssertionError("Retry loop ended unexpectedly")

    @staticmethod
    def _validate(text: str, validator: Callable[[str], None]) -> None:
        try:
            validator(text)
        except (ValueError, TypeError, KeyError):
            raise ProviderError("Provider response did not match the task schema") from None
