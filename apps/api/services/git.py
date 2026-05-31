"""Intégration GitHub — commits / branches / PRs d'un dépôt "owner/name".

API publique GitHub (60 req/h sans token ; définir GITHUB_TOKEN pour 5000/h).
Cache mémoire TTL pour éviter de cogner la limite à chaque ouverture de projet.
"""
import time

import httpx

from apps.api.core.config import settings

GH = "https://api.github.com"
_cache: dict[str, tuple[float, dict]] = {}
_TTL = 60.0


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "mission-control"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def fetch_git(repo: str) -> dict:
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    now = time.monotonic()
    hit = _cache.get(repo)
    if hit and now - hit[0] < _TTL:
        return hit[1]

    try:
        with httpx.Client(timeout=8.0, headers=_headers()) as c:
            meta = c.get(f"{GH}/repos/{repo}")
            if meta.status_code != 200:
                return {"repo": repo, "error": f"GitHub {meta.status_code}", "available": False}
            m = meta.json()
            commits = c.get(f"{GH}/repos/{repo}/commits", params={"per_page": 5}).json()
            branches = c.get(f"{GH}/repos/{repo}/branches", params={"per_page": 100}).json()
            pulls = c.get(f"{GH}/repos/{repo}/pulls", params={"state": "open", "per_page": 20}).json()
    except httpx.HTTPError as exc:
        return {"repo": repo, "error": str(exc), "available": False}

    data = {
        "repo": repo,
        "available": True,
        "url": m.get("html_url"),
        "default_branch": m.get("default_branch"),
        "stars": m.get("stargazers_count", 0),
        "open_issues": m.get("open_issues_count", 0),
        "branch_count": len(branches) if isinstance(branches, list) else 0,
        "branches": [b["name"] for b in branches][:24] if isinstance(branches, list) else [],
        "commits": [
            {
                "sha": x["sha"][:7],
                "message": (x["commit"]["message"].splitlines() or [""])[0][:100],
                "author": (x["commit"].get("author") or {}).get("name", "?"),
                "date": (x["commit"].get("author") or {}).get("date"),
            }
            for x in (commits if isinstance(commits, list) else [])[:5]
        ],
        "prs": [
            {"number": p["number"], "title": p["title"][:100], "user": (p.get("user") or {}).get("login", "?")}
            for p in (pulls if isinstance(pulls, list) else [])
        ],
    }
    _cache[repo] = (now, data)
    return data
