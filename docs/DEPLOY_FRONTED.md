# Déploiement prod — mode co-hébergé (`ag.infinityauh.com`)

> Runbook copiable, calqué sur celui de GuardianOps (`Agent_Audit_Secu_SI/docs/runbook.md` §« Serveur
> CO-HÉBERGÉ »). Ce projet n'a **pas** ses propres 80/443 disponibles sur le VPS partagé
> (`51.210.40.198`) — déjà pris par SGI (`os.infinityauh.com`). C'est le **Caddy de SGI** qui
> reverse-proxy directement vers `ag-web`/`ag-api` via le réseau Docker externe partagé `caddy_net`.

## 0. Pré-requis

- Accès SSH root/sudo au VPS partagé (celui de SGI/`os.infinityauh.com`, `go.infinityauh.com`).
- Le réseau externe `caddy_net` existe déjà (créé par le `docker-compose.prod.yml` de SGI).
- Docker Compose ≥ 2.24 (tag de fusion `!override`, déjà utilisé dans `docker-compose.prod.yml`).

## 1. DNS (avant tout — Caddy exige le DNS pour le certificat, côté SGI)

Deux enregistrements **A** vers l'IP du VPS partagé :
- `ag.infinityauh.com` → dashboard
- `api.ag.infinityauh.com` → API

```bash
dig +short ag.infinityauh.com api.ag.infinityauh.com   # doivent renvoyer l'IP du VPS
```

## 2. Code + secrets (sur le VPS)

```bash
git clone https://github.com/HichamSADIKI/mission-control-platform.git mission-control
cd mission-control
cp infra/.env.prod.example infra/.env.prod
# Génère de VRAIS secrets :
python3 -c "import secrets; print('JWT_SECRET='+secrets.token_hex(32))"      >> /tmp/mc-secrets
python3 -c "import secrets; print('MC_INGEST_TOKEN='+secrets.token_hex(32))" >> /tmp/mc-secrets
echo       "POSTGRES_PASSWORD=$(openssl rand -base64 24)"                    >> /tmp/mc-secrets
cat /tmp/mc-secrets    # recopie ces valeurs dans infra/.env.prod, puis :
shred -u /tmp/mc-secrets 2>/dev/null || rm -f /tmp/mc-secrets
chmod 600 infra/.env.prod
```

## 3. Démarrer la stack (sans exposition publique propre)

```bash
docker network inspect caddy_net >/dev/null 2>&1 || docker network create caddy_net

docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml \
               -f infra/docker-compose.prod-fronted.yml --env-file infra/.env.prod \
               up -d --build postgres redis ag-api ag-web
```
`ag-api`/`ag-web` rejoignent `caddy_net` sans publier aucun port sur l'hôte (`ports: !override []`).
Les migrations + garde anti-seed-démo tournent automatiquement dans `infra/api-entrypoint.sh`
(`ENVIRONMENT=prod` → seed sauté, pas de `--reload`).

## 4. Vérifier l'absence de compte démo, puis créer le vrai admin

```bash
docker compose -f infra/docker-compose.yml exec -T postgres \
  psql -U mc -d mission_control -tAc \
  "SELECT count(*) FROM users WHERE email='demo@infinity.ae';"   # attendu : 0

docker compose -f infra/docker-compose.yml exec ag-api \
  python -m apps.api.create_admin \
  --email admin@infinityauh.com --password 'MotDePasseFort' --name "Admin"
```
Idempotent (relançable sans dupliquer).

## 5. Côté SGI (hôte Caddy) — active le routage

Une fois `AG_DOMAIN`/`AG_API_DOMAIN` posés dans `.env.prod` de SGI (cf. sa PR `feat/caddy-route-
ag-infinityauh`, bloc Caddyfile `AGENT CONTROL` déjà prêt) :

```bash
# Dans le checkout SGI, .env.prod += :
#   AG_DOMAIN=ag.infinityauh.com
#   AG_API_DOMAIN=api.ag.infinityauh.com
docker compose -f docker-compose.prod.yml up -d --force-recreate caddy
```
⚠️ `--force-recreate caddy` est **indispensable** (un simple `up -d` ne recrée pas Caddy sur un
changement du Caddyfile bind-monté → certificat jamais obtenu).

## 6. Vérifications

```bash
curl -s  https://ag.infinityauh.com/                 # page de login (pas de mock)
curl -s  https://api.ag.infinityauh.com/health        # {"status":"ok"}
curl -sI https://api.ag.infinityauh.com/health | grep -i strict-transport   # HSTS présent
```
Ouvre `https://ag.infinityauh.com` → login avec l'admin créé à l'étape 4.

Heartbeat de test (depuis n'importe quelle machine, avec le vrai `MC_INGEST_TOKEN`) :
```bash
MC_API_URL=https://api.ag.infinityauh.com MC_INGEST_TOKEN=<le vrai token> \
  PYTHONPATH=apps/agent-cli python3 -m mc_platform working "smoke test" 1 0 1
```
→ doit apparaître en direct dans le dashboard (WS).

## 7. Mises à jour applicatives

```bash
cd mission-control && git pull
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml \
               -f infra/docker-compose.prod-fronted.yml --env-file infra/.env.prod \
               up -d --build postgres redis ag-api ag-web
```
Pas besoin de recréer le Caddy de SGI sauf si le Caddyfile de SGI change lui-même.

## Dépannage rapide

- **502 sur ag.infinityauh.com** : `ag-web`/`ag-api` ne sont pas (encore) sur `caddy_net` — vérifie
  `docker network inspect caddy_net` côté VPS, doit lister les 2 conteneurs.
- **Caddy (SGI) n'obtient pas le certificat** : le DNS doit pointer sur le VPS AVANT le
  `--force-recreate caddy` ; `docker compose -f docker-compose.prod.yml logs caddy` côté SGI.
- **`ENVIRONMENT` requis manquant** : le compose refuse de démarrer si `JWT_SECRET` /
  `MC_INGEST_TOKEN` / `POSTGRES_PASSWORD` ne sont pas dans `infra/.env.prod` (fail-closed
  volontaire, cf. `docker-compose.prod.yml`).

## Checklist go-live

- [ ] DNS A `ag.infinityauh.com` + `api.ag.infinityauh.com` → VPS
- [ ] `infra/.env.prod` avec de vrais secrets (jamais committé)
- [ ] stack up (postgres + redis + ag-api + ag-web, sur `caddy_net`)
- [ ] **0 compte démo** (`demo@infinity.ae` absent)
- [ ] admin réel créé (`create_admin.py`)
- [ ] Caddyfile SGI recréé (`--force-recreate caddy`) → HTTPS + HSTS OK
- [ ] heartbeat de test visible en direct dans le dashboard
