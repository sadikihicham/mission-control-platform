"""Tests du CLI contre un MOCK du Contract D (serveur HTTP stdlib).

Lancement : `python -m pytest apps/agent-cli/tests` (avec apps/agent-cli sur PYTHONPATH)
ou simplement `python apps/agent-cli/tests/test_client.py` (runner intégré).
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mc_platform import client  # noqa: E402
from mc_platform.cli import main  # noqa: E402

CAPTURED: dict = {}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        CAPTURED["path"] = self.path
        CAPTURED["token"] = self.headers.get("X-MC-Token")
        CAPTURED["body"] = json.loads(self.rfile.read(length) or b"{}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *args):  # silence
        pass


def _serve():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _setup_env(srv):
    host, port = srv.server_address
    os.environ["MC_API_URL"] = f"http://{host}:{port}"
    os.environ["MC_INGEST_TOKEN"] = "test-token"
    os.environ["MC_AGENT_KEY"] = "test-agent"
    os.environ.pop("MC_PROJECT", None)


def test_build_payload_contract_d():
    p = client.build_payload(
        "working", agent="a1", task="t", progress=45, tasks_done=3, tasks_total=7, module="M5"
    )
    assert p == {
        "agent": "a1", "state": "working", "task": "t",
        "progress": 45, "tasks_done": 3, "tasks_total": 7, "module": "M5",
    }
    # champs non fournis absents
    assert "blocker" not in p and "branch" not in p


def test_invalid_state_rejected():
    try:
        client.build_payload("stale")  # 'stale' est dérivé serveur, pas émis
    except ValueError:
        return
    raise AssertionError("état 'stale' aurait dû être rejeté")


def test_post_hits_endpoint_with_token(srv):
    _setup_env(srv)
    status, _ = client.send(client.build_payload("working", task="hello", progress=10))
    assert status == 200
    assert CAPTURED["path"] == "/agents/heartbeat"
    assert CAPTURED["token"] == "test-token"
    assert CAPTURED["body"]["agent"] == "test-agent"
    assert CAPTURED["body"]["state"] == "working"
    assert CAPTURED["body"]["task"] == "hello"


def test_cli_working_and_blocked(srv):
    _setup_env(srv)
    assert main(["working", "coding", "50", "2", "4"]) == 0
    assert CAPTURED["body"]["state"] == "working"
    assert CAPTURED["body"]["progress"] == 50
    assert CAPTURED["body"]["tasks_total"] == 4

    assert main(["blocked", "need DB"]) == 0
    assert CAPTURED["body"]["state"] == "blocked"
    assert CAPTURED["body"]["blocker"] == "need DB"


def test_unreachable_is_non_blocking():
    os.environ["MC_API_URL"] = "http://127.0.0.1:1"  # port mort
    status, _ = client.send(client.build_payload("done", progress=100))
    assert status is None  # injoignable → pas d'exception


# --- runner minimal sans pytest (Python 3.14 local) ---
if __name__ == "__main__":
    srv = _serve()
    passed = 0
    test_build_payload_contract_d(); passed += 1
    test_invalid_state_rejected(); passed += 1
    test_post_hits_endpoint_with_token(srv); passed += 1
    test_cli_working_and_blocked(srv); passed += 1
    test_unreachable_is_non_blocking(); passed += 1
    print(f"OK — {passed} tests passés")
