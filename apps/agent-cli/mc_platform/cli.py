"""CLI ergonomique `mc-platform` (argparse, stdlib).

Commandes :
  report   --state ... [--task --progress --done --total --module --branch --blocker]
  working  "<task>" [progress] [done] [total]
  blocked  "<reason>"
  done     [progress=100]
  idle
  beat     (rafraîchit l'horodatage, conserve le reste côté serveur)

Sortie non bloquante : si l'API est injoignable, un avertissement est affiché
mais le code de sortie reste 0 (un heartbeat ne doit jamais casser un agent).
"""
import argparse
import sys

from mc_platform import client


def _emit(payload: dict, *, quiet: bool = False) -> int:
    status, body = client.send(payload)
    if status is None:
        if not quiet:
            print(f"⚠ mc-platform: API injoignable ({body})", file=sys.stderr)
        return 0
    if status >= 400:
        print(f"⚠ mc-platform: {status} {body}", file=sys.stderr)
        return 0
    if not quiet:
        print(f"✓ {payload['state']} → {client.config()['api_url']} ({status})")
    return 0


def _int_or_none(v):
    return int(v) if v is not None else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mc-platform", description="Heartbeat agent → Mission Control")
    sub = p.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("report", help="report complet")
    rp.add_argument("--state", required=True, choices=sorted(client.VALID_STATES))
    rp.add_argument("--task")
    rp.add_argument("--progress", type=int)
    rp.add_argument("--done", type=int, dest="tasks_done")
    rp.add_argument("--total", type=int, dest="tasks_total")
    rp.add_argument("--module")
    rp.add_argument("--branch")
    rp.add_argument("--blocker")

    wk = sub.add_parser("working", help='working "<task>" [progress] [done] [total]')
    wk.add_argument("task")
    wk.add_argument("progress", nargs="?", type=int)
    wk.add_argument("done", nargs="?", type=int)
    wk.add_argument("total", nargs="?", type=int)

    bl = sub.add_parser("blocked", help='blocked "<reason>"')
    bl.add_argument("reason")

    dn = sub.add_parser("done", help="done [progress=100]")
    dn.add_argument("progress", nargs="?", type=int, default=100)

    sub.add_parser("idle", help="état idle")
    sub.add_parser("beat", help="heartbeat (working, rafraîchit l'horodatage)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "report":
        payload = client.build_payload(
            args.state, task=args.task, progress=args.progress,
            tasks_done=args.tasks_done, tasks_total=args.tasks_total,
            module=args.module, branch=args.branch, blocker=args.blocker,
        )
    elif args.cmd == "working":
        payload = client.build_payload(
            "working", task=args.task, progress=args.progress,
            tasks_done=args.done, tasks_total=args.total,
        )
    elif args.cmd == "blocked":
        payload = client.build_payload("blocked", blocker=args.reason)
    elif args.cmd == "done":
        payload = client.build_payload("done", progress=args.progress)
    elif args.cmd == "idle":
        payload = client.build_payload("idle")
    elif args.cmd == "beat":
        payload = client.build_payload("working")
    else:  # pragma: no cover
        return 2

    return _emit(payload, quiet=(args.cmd == "beat"))


if __name__ == "__main__":
    raise SystemExit(main())
