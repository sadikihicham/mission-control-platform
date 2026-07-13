"""CLI de bootstrap admin prod-safe (idempotent) — pas de compte démo.

Contrairement à `seed.py` (comptes de démo, mots de passe faibles, réservé au dev/test), ce script
crée UN SEUL compte admin réel à partir d'un mot de passe fourni par l'opérateur. Nécessaire en
prod dès que le seed démo est désactivé (`ENVIRONMENT=prod`, cf. `infra/api-entrypoint.sh`) : sans
lui, aucun moyen de se connecter au premier démarrage.

Lancement (dans le conteneur `ag-api`) :
    python -m apps.api.create_admin --email admin@exemple.com --name "Admin"
    (invite le mot de passe via un prompt caché — `--password` reste dispo pour un usage scripté,
    mais le laisser en argument CLI le rend visible dans l'historique shell et `ps aux`)
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from apps.api.core.db import get_sessionmaker
from apps.api.core.security import hash_password
from apps.api.models import User

MIN_PASSWORD_LENGTH = 12


def run(email: str, password: str, name: str, civility: str | None) -> None:
    Session = get_sessionmaker()
    with Session() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            print(f"~ {email} existe déjà (rôle {existing.role}) — rien à faire (idempotent)")
            return
        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                role="admin",
                full_name=name,
                civility=civility,
            )
        )
        db.commit()
    print(f"+ admin {email} créé")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap d'un compte admin prod-safe (idempotent).")
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--password", default=None,
        help="Évite si possible : visible dans l'historique shell/ps aux. Omis → prompt caché.",
    )
    parser.add_argument("--name", required=True, help="Nom affiché (full_name)")
    parser.add_argument("--civility", choices=["mr", "mrs", "miss"], default=None)
    args = parser.parse_args()

    password = args.password or getpass.getpass("Mot de passe admin : ")

    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"refuse : mot de passe < {MIN_PASSWORD_LENGTH} caractères", file=sys.stderr)
        raise SystemExit(1)

    run(args.email, password, args.name, args.civility)


if __name__ == "__main__":
    main()
