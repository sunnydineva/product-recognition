#!/bin/sh
set -eu
# Never enable shell tracing here: credentials are environment-only.
fail() { echo "$1" >&2; exit 1; }
case "${1:-}" in
    --fresh|--existing) mode=$1 ;;
    *) fail "Usage: provision.sh --fresh|--existing (existing requires explicit opt-in)" ;;
esac
[ "$#" -eq 1 ] || fail "Unexpected arguments"
: "${POSTGRES_USER:?Required}" "${POSTGRES_DB:?Required}"
: "${INVENTORY_DB:?Required}" "${INVENTORY_DB_USER:?Required}" "${INVENTORY_DB_PASSWORD:?Required}"
identifier() {
    case "$1" in ''|[!a-z_]*|*[!a-z0-9_]*) fail "Use lowercase SQL identifiers only" ;; esac
    [ "${#1}" -le 63 ] || fail "SQL identifier too long"
}
for value in "$POSTGRES_USER" "$POSTGRES_DB" "$INVENTORY_DB" "$INVENTORY_DB_USER"; do identifier "$value"; done
case "$INVENTORY_DB" in postgres|template0|template1) fail "Reserved inventory database" ;; esac
[ "$INVENTORY_DB" != "$POSTGRES_DB" ] || fail "Databases must be distinct"
[ "$INVENTORY_DB_USER" != "$POSTGRES_USER" ] || fail "Inventory role must differ from administrator/legacy AI owner"
if [ "$mode" = --fresh ]; then
    : "${AI_DB_USER:?Fresh initialization requires AI_DB_USER}" "${AI_DB_PASSWORD:?Required}"
    identifier "$AI_DB_USER"
    [ "$AI_DB_USER" != "$POSTGRES_USER" ] || fail "AI role must differ from administrator"
    [ "$AI_DB_USER" != "$INVENTORY_DB_USER" ] || fail "Service roles must be distinct"
elif [ -n "${AI_DB_USER:-}" ]; then
    [ "$AI_DB_USER" != "$INVENTORY_DB_USER" ] || fail "Service roles must be distinct"
fi

# Use the local socket and the existing cluster administrator. No passwords in
# argv or generated files. psql quotes variables as SQL literals / identifiers.
psql -X --no-password --username "$POSTGRES_USER" --dbname postgres \
    --set=ON_ERROR_STOP=1 --file=/opt/database/provision-inventory.sql

if [ "$mode" = --fresh ]; then
    psql -X --no-password --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        --set=ON_ERROR_STOP=1 --file=/opt/database/provision-ai-fresh.sql
fi
