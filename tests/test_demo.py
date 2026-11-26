import http.client
from threading import Thread

import pytest

from trace_mem.demo import Handler, ThreadingHTTPServer, archive, sample


def values(policy, cap, step, query):
    return {fact["value"] for fact in sample(policy, cap, step, query)["facts"]}


def test_replay_correction_uncertainty_budget_history_and_forgetting():
    assert values("B3", 1, 2, 2) == {"Cedar Hall", "Blue envelope"}
    assert values("B3", 1, 5, 5) == {"Maple Studio"}
    assert values("B3", 1, 5, 2) == {"Cedar Hall"}
    assert values("B2", 1, 5, 5) == values("B3", 0, 5, 5) == {"Cedar Hall"}
    result = sample("B3", 1, 5, 5)
    assert result["stats"]["calls"] == 1
    assert result["facts"][0]["source"] == "3/1"
    assert result["timeline"][-1]["operations"] == ["delete"]
    assert result == sample("B3", 1, 5, 5)
    with pytest.raises(ValueError):
        sample("B3", 1, 2, 3)


def test_dashboard_archive_preserves_modes_denominators_and_directions():
    data = archive()
    assert data["cohort"] == {"histories": 100, "families": 10}
    pair = {(r["mode"], r["budget"]): r["difference"] for r in data["contrasts"]
            if r["left"] == "T2" and r["right"] == "H-paced"}
    assert pair["fixed", 50] < 0 < pair["closed-loop", 50]
    assert data["external"]["BM25"]["completed"] == 14
    assert data["external"]["T2-2"]["completed"] == 1


def test_http_allowlist_and_input_validation():
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(path, headers=None):
                with_connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    with_connection.request("GET", path, headers=headers or {})
                    response = with_connection.getresponse()
                    return response.status, response.getheaders(), response.read()
                finally:
                    with_connection.close()

            status, headers, body = request("/")
            assert status == 200 and b"Replay lab" in body
            assert dict(headers)["Cache-Control"] == "no-store"
            assert request("/api/archive")[0] == 200
            assert request("/api/replay?policy=B3&cap=1&step=5&query=3")[0] == 200
            assert request("/api/replay?policy=B3&cap=1&step=5&query=6")[0] == 400
            assert request("/api/replay?policy=B3&cap=1&step=5&query=3&query=4")[0] == 400
            assert request("/%2e%2e/.env")[0] == 404
            assert request("/", {"Host": "untrusted.example"})[0] == 403
        finally:
            server.shutdown()
            thread.join(timeout=5)
