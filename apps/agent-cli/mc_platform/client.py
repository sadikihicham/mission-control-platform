"""Construction du payload Contract D + envoi HTTP (stdlib uniquement).

Config par environnement :
  MC_API_URL       (def http://localhost:8000)  base de l'API
  MC_INGEST_TOKEN  (def dev-ingest-token)        header X-MC-Token (secret d'enrôlement)
  MC_AGENT_KEY     (def agent)                   identifiant de l'agent
  MC_PROJECT       (optionnel)                    slug du projet
  MC_TOKEN_FILE    (def ~/.mc-platform/credentials.json) token par agent, une fois enrôlé

Enrôlement (Contract D) : ce client envoie X-MC-Enroll: 1. Au 1er heartbeat d'un
agent_key, le serveur émet un token propre à cet agent (`agent_token` dans la réponse) ;
ce client le persiste dans MC_TOKEN_FILE et l'utilise ensuite à la place du secret
partagé MC_INGEST_TOKEN pour cet agent_key. Ne bloque jamais un heartbeat si la
persistance échoue (disque plein, dossier non accessible, etc.).
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

HEARTBEAT_PATH = "/agents/heartbeat"
VALID_STATES = {"idle", "working", "blocked", "done", "error"}


def _credentials_path() -> Path:
    return Path(
        os.environ.get("MC_TOKEN_FILE") or os.path.expanduser("~/.mc-platform/credentials.json")
    )


def _load_token(agent_key: str) -> str | None:
    try:
        data = json.loads(_credentials_path().read_text())
        token = data.get(agent_key)
        return token if isinstance(token, str) and token else None
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def _store_token(agent_key: str, token: str) -> None:
    path = _credentials_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError):
            data = {}
        data[agent_key] = token
        path.write_text(json.dumps(data))
        path.chmod(0o600)
    except OSError:
        pass  # la persistance du token n'est jamais bloquante pour un heartbeat


def config() -> dict:
    return {
        "api_url": os.environ.get("MC_API_URL", "http://localhost:8000").rstrip("/"),
        "token": os.environ.get("MC_INGEST_TOKEN", "dev-ingest-token"),
        "agent": os.environ.get("MC_AGENT_KEY", "agent"),
        "project": os.environ.get("MC_PROJECT"),
    }


def build_payload(
    state: str,
    *,
    agent: str | None = None,
    project: str | None = None,
    task: str | None = None,
    progress: int | None = None,
    tasks_done: int | None = None,
    tasks_total: int | None = None,
    module: str | None = None,
    branch: str | None = None,
    blocker: str | None = None,
    meta: dict | None = None,
) -> dict:
    """Construit un payload Contract D. Seuls les champs fournis sont inclus."""
    if state not in VALID_STATES:
        raise ValueError(f"état invalide: {state!r} (attendu: {sorted(VALID_STATES)})")
    cfg = config()
    payload: dict = {"agent": agent or cfg["agent"], "state": state}
    proj = project or cfg["project"]
    if proj:
        payload["project"] = proj
    optional = {
        "task": task, "progress": progress, "tasks_done": tasks_done,
        "tasks_total": tasks_total, "module": module, "branch": branch, "blocker": blocker,
    }
    for key, value in optional.items():
        if value is not None:
            payload[key] = value
    if meta:
        payload["meta"] = meta
    return payload


def send(payload: dict, *, timeout: float = 3.0) -> tuple[int | None, str]:
    """POST le payload sur {api}/agents/heartbeat. Ne lève jamais : renvoie
    (status|None, body). status None = API injoignable (heartbeat non bloquant)."""
    cfg = config()
    agent_key = payload.get("agent") or cfg["agent"]
    token = _load_token(agent_key) or cfg["token"]
    url = f"{cfg['api_url']}{HEARTBEAT_PATH}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-MC-Token": token,
            "X-MC-Enroll": "1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, body = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        return None, str(exc)

    if 200 <= status < 300:
        try:
            issued = json.loads(body).get("agent_token")
        except (json.JSONDecodeError, AttributeError):
            issued = None
        if issued:
            _store_token(agent_key, issued)
    return status, body
