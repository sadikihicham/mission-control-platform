"""Tests du CLI contre un MOCK du Contract D (serveur HTTP stdlib).

Lancement : `python -m pytest apps/agent-cli/tests` (avec apps/agent-cli sur PYTHONPATH)
ou simplement `python apps/agent-cli/tests/test_client.py` (runner intégré).
"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mc_platform import client  # noqa: E402
from mc_platform.cli import main  # noqa: E402

CAPTURED: dict = {}
# Rempli par un test pour faire répondre le mock avec un agent_token (Contract D,
# enrôlement). Vide = comportement par défaut (pas de token émis).
RESPOND_WITH: dict = {}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        CAPTURED["path"] = self.path
        CAPTURED["token"] = self.headers.get("X-MC-Token")
        CAPTURED["enroll"] = self.headers.get("X-MC-Enroll")
        CAPTURED["body"] = json.loads(self.rfile.read(length) or b"{}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = {"ok": True}
        if RESPOND_WITH.get("agent_token"):
            body["agent_token"] = RESPOND_WITH["agent_token"]
        self.wfile.write(json.dumps(body).encode("utf-8"))

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
    # Fichier de credentials frais à chaque test — jamais le vrai ~/.mc-platform/,
    # et jamais de fuite d'un token enrôlé par un test précédent vers un autre.
    token_file = Path(tempfile.gettempdir()) / "mc-platform-test-credentials.json"
    token_file.unlink(missing_ok=True)
    os.environ["MC_TOKEN_FILE"] = str(token_file)
    RESPOND_WITH.clear()


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
    assert CAPTURED["enroll"] == "1"
    assert CAPTURED["body"]["agent"] == "test-agent"
    assert CAPTURED["body"]["state"] == "working"
    assert CAPTURED["body"]["task"] == "hello"


def test_agent_token_persisted_and_reused(srv):
    _setup_env(srv)
    token_file = Path(os.environ["MC_TOKEN_FILE"])
    RESPOND_WITH["agent_token"] = "secret-agent-token"

    status, _ = client.send(client.build_payload("working", task="hello"))
    assert status == 200
    assert CAPTURED["token"] == "test-token"  # 1er appel : encore le secret partagé
    assert json.loads(token_file.read_text()) == {"test-agent": "secret-agent-token"}

    RESPOND_WITH.pop("agent_token", None)  # le serveur n'en réémet plus une fois enrôlé
    client.send(client.build_payload("working", task="again"))
    assert CAPTURED["token"] == "secret-agent-token"  # 2e appel : son propre token


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
    test_agent_token_persisted_and_reused(srv); passed += 1
    test_cli_working_and_blocked(srv); passed += 1
    test_unreachable_is_non_blocking(); passed += 1
    print(f"OK — {passed} tests passés")
