#!/bin/sh
# Fix /data ownership (bind mounts arrive as root on Linux) and drop privileges.
set -eu

DATA_DIR="${MILVUS_LITE_DATA_DIR:-/data}"
HOST="${MILVUS_LITE_HOST:-0.0.0.0}"
PORT="${MILVUS_LITE_PORT:-19530}"
RUN_UID=10001
RUN_GID=10001

# Only the default `milvus-lite server` command gets the env-driven flags;
# any other command (dump, python -c, shell) is passed through untouched.
if [ "${1:-}" = "milvus-lite" ] && [ "${2:-}" = "server" ]; then
    shift 2
    set -- milvus-lite server --data-dir "$DATA_DIR" --host "$HOST" --port "$PORT" "$@"
fi

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    if [ "$(stat -c '%u:%g' "$DATA_DIR" 2>/dev/null || echo '?')" != "${RUN_UID}:${RUN_GID}" ]; then
        chown -R "${RUN_UID}:${RUN_GID}" "$DATA_DIR"
    fi
    exec gosu "${RUN_UID}:${RUN_GID}" "$@"
fi

exec "$@"
