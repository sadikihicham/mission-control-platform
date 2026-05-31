"""Construction du payload Contract D + envoi HTTP (stdlib uniquement).

Config par environnement :
  MC_API_URL       (def http://localhost:8000)  base de l'API
  MC_INGEST_TOKEN  (def dev-ingest-token)        header X-MC-Token
  MC_AGENT_KEY     (def agent)                   identifiant de l'agent
  MC_PROJECT       (optionnel)                    slug du projet
"""
import json
import os
import urllib.error
import urllib.request

HEARTBEAT_PATH = "/agents/heartbeat"
VALID_STATES = {"idle", "working", "blocked", "done", "error"}


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
    url = f"{cfg['api_url']}{HEARTBEAT_PATH}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "X-MC-Token": cfg["token"]},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        return None, str(exc)
