#!/usr/bin/env bash
# Répétition de restauration + RÉPÉTITION DES MIGRATIONS — Agent Control (ag.infinityauh.com).
# « Un backup jamais restauré n'est pas un filet, c'est un espoir. »
#
# Ce que ce script prouve, dans cet ordre, SANS JAMAIS TOUCHER À LA BASE DE PROD :
#   1. le dump est réellement restaurable (pas juste « le fichier fait N Mo ») ;
#   2. on MESURE, sur la copie, ce que la migration 0007 va détruire (colonnes
#      `company_id` de `users`/`projects`) — avant qu'elle ne le détruise ;
#   3. les 10 migrations (0007→0016) passent RÉELLEMENT sur les données de prod.
#
# Le tout dans une base TEMPORAIRE du cluster prod, supprimée en sortie même en cas
# d'erreur (trap). La PII ne quitte pas le VPS. Pas de 2ᵉ Postgres jetable : sur ce
# type de VPS un second cluster se fait tuer (rc 137) pendant un restore concurrent.
#
# ⚠️ SÉQUENCEMENT — le piège que ce garde attrape :
#   l'image `ag-api` DÉPLOYÉE ne contient PAS les migrations 0008→0016. Rejouer la
#   répétition avec elle ne prouverait RIEN (elle s'arrêterait à la tête qu'elle
#   connaît, en affichant un vert mensonger). Il faut donc AVOIR CONSTRUIT l'image
#   cible AVANT : `git reset --hard origin/main && docker compose … build ag-api`.
#   Le script REFUSE de tourner si l'image ne connaît pas la tête cible (§ GARDE).
#
# Usage (SUR LE VPS, depuis ~/mission-control) :
#   1) sauvegarde :  ./infra/restore-drill.sh --dump        → ~/mc-backups/mc-pre-<date>.dump
#   2) répétition :  ./infra/restore-drill.sh [chemin/du/dump]
# Sortie : 0 = déploiement sûr sur ces données · 1 = NE PAS DÉPLOYER.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

C="docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml \
-f infra/docker-compose.prod-fronted.yml --env-file infra/.env.prod"
TARGET_HEAD="0016_project_task_install_id"
BKDIR="$HOME/mc-backups"

psql_prod() { $C exec -T postgres psql -U mc -d mission_control -tAc "$1" 2>/dev/null | tr -d '[:space:]'; }
psql_drill() { $C exec -T postgres psql -U mc -d "$DDB" -tAc "$1" 2>/dev/null | tr -d '[:space:]'; }

# ---------------------------------------------------------------- mode sauvegarde
if [ "${1:-}" = "--dump" ]; then
	mkdir -p "$BKDIR"
	OUT="$BKDIR/mc-pre-$(date +%Y%m%d-%H%M%S).dump"
	# -Fc (format custom) et non `| gzip` : restaurable par pg_restore, sélectif,
	# et il porte sa propre somme de contrôle de cohérence.
	if $C exec -T postgres pg_dump -U mc -d mission_control -Fc >"$OUT"; then
		echo "✓ dump : $OUT ($(du -h "$OUT" | cut -f1))"
		echo "  → répétition : $0 $OUT"
		exit 0
	fi
	echo "✗ pg_dump a échoué — pas de dump exploitable, NE PAS DÉPLOYER." >&2
	rm -f "$OUT"
	exit 1
fi

# ------------------------------------------------------------------------ GARDE
# L'image cible connaît-elle la tête visée ? Sinon la répétition serait un faux vert.
echo "→ garde : l'image ag-api connaît-elle $TARGET_HEAD ?"
HEADS=$($C run --rm --no-deps --entrypoint alembic ag-api heads 2>/dev/null)
case "$HEADS" in
*"$TARGET_HEAD"*) echo "  ✓ image à jour" ;;
*)
	echo "✗ REFUS : l'image ag-api ne connaît pas $TARGET_HEAD (têtes vues : ${HEADS:-∅})."
	echo "  → construire l'image cible d'abord :"
	echo "     git reset --hard origin/main && $C build ag-api"
	exit 1
	;;
esac

# ------------------------------------------------------------------- restauration
BK="${1:-$(ls -t "$BKDIR"/mc-pre-*.dump 2>/dev/null | head -1)}"
[ -z "${BK:-}" ] && {
	echo "✗ aucun dump (ni argument, ni $BKDIR/mc-pre-*.dump) — lancer d'abord : $0 --dump"
	exit 1
}
[ -f "$BK" ] || {
	echo "✗ dump introuvable : $BK"
	exit 1
}
echo "→ dump testé : $BK ($(du -h "$BK" | cut -f1))"

DDB="restore_drill_$$"
cleanup() { $C exec -T postgres psql -U mc -d mission_control \
	-c "DROP DATABASE IF EXISTS $DDB WITH (FORCE)" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "→ base temporaire isolée : $DDB"
$C exec -T postgres psql -U mc -d mission_control -c "CREATE DATABASE $DDB" >/dev/null || {
	echo "✗ création de la base temporaire impossible"
	exit 1
}

echo "→ pg_restore"
ERR="/tmp/mc-restore-drill.$$.err"
if ! $C exec -T postgres pg_restore -U mc -d "$DDB" --no-owner --no-acl <"$BK" 2>"$ERR"; then
	echo "✗ pg_restore a échoué :"
	tail -8 "$ERR"
	rm -f "$ERR"
	exit 1
fi
rm -f "$ERR"

BEFORE_HEAD=$(psql_drill "SELECT version_num FROM alembic_version")
TABLES=$(psql_drill "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
USERS=$(psql_drill "SELECT count(*) FROM users")
echo "  tête alembic restaurée : ${BEFORE_HEAD:-∅} · tables : ${TABLES:-0} · users : ${USERS:-0}"
if [ -z "$BEFORE_HEAD" ] || [ "${TABLES:-0}" -lt 5 ] || [ "${USERS:-0}" -lt 1 ]; then
	echo "✗ RESTAURATION ROUGE — contenu insuffisant : ce dump N'EST PAS un filet fiable."
	exit 1
fi

# -------------------------------------- mesure de ce que 0007 va détruire (P3)
# Se fait ICI, sur la copie, AVANT l'upgrade : après, la colonne n'existe plus.
echo "→ mesure de la perte de 0007 (drop de users.company_id / projects.company_id)"
LOST_U=$(psql_drill "SELECT count(*) FROM users WHERE company_id IS NOT NULL")
LOST_P=$(psql_drill "SELECT count(*) FROM projects WHERE company_id IS NOT NULL")
echo "  users.company_id renseignés    : ${LOST_U:-0}"
echo "  projects.company_id renseignés : ${LOST_P:-0}"
if [ "${LOST_U:-0}" != "0" ] || [ "${LOST_P:-0}" != "0" ]; then
	echo '  ⚠️  des valeurs SERONT perdues. Le downgrade() de 0007 recrée la COLONNE, pas les VALEURS.'
	echo "      Seule la restauration du dump les récupère → garder $BK hors-site."
fi

# ------------------------------------------------- répétition des 10 migrations
echo "→ alembic upgrade head sur la copie (répétition réelle des 10 migrations)"
DBURL=$($C exec -T ag-api printenv DATABASE_URL 2>/dev/null | tr -d '\r\n')
[ -z "$DBURL" ] && {
	echo "✗ DATABASE_URL illisible depuis ag-api (le service tourne-t-il ?)"
	exit 1
}
DRILL_URL="${DBURL%/mission_control}/$DDB"
if ! $C run --rm --no-deps -e "DATABASE_URL=$DRILL_URL" \
	--entrypoint alembic ag-api upgrade head; then
	echo "✗ RÉPÉTITION ROUGE — les migrations ÉCHOUENT sur les données de prod."
	echo "  Déployer maintenant laisserait l'API en boucle de redémarrage (entrypoint : set -e)."
	exit 1
fi

AFTER_HEAD=$(psql_drill "SELECT version_num FROM alembic_version")
INSTALLS=$(psql_drill "SELECT count(*) FROM mc_installations")
echo "  tête après migration : ${AFTER_HEAD:-∅} · mc_installations : ${INSTALLS:-0}"

if [ "$AFTER_HEAD" = "$TARGET_HEAD" ] && [ "${INSTALLS:-0}" -ge 1 ]; then
	echo "✓ VERT — dump restaurable ET 10 migrations rejouées sur les données réelles."
	echo "  ($BEFORE_HEAD → $AFTER_HEAD · perte 0007 mesurée : $LOST_U user(s), $LOST_P projet(s))"
	exit 0
fi
echo "✗ ROUGE — tête finale inattendue (${AFTER_HEAD:-∅} ≠ $TARGET_HEAD) ou installation locale absente."
exit 1
