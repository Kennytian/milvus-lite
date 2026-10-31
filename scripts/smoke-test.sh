#!/usr/bin/env bash
# Smoke test for a locally built image: server up -> write -> restart -> verify.
# Usage: scripts/smoke-test.sh [image]   (default: milvus-lite:smoke)
set -euo pipefail

IMAGE="${1:-milvus-lite:smoke}"
NAME="milvus-lite-smoke"
PORT=19530
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

echo "==> starting $IMAGE"
docker run -d --name "$NAME" --network host "$IMAGE" >/dev/null

echo "==> waiting for the gRPC port"
for _ in $(seq 1 60); do
    if docker exec "$NAME" python -c "import socket; socket.create_connection(('127.0.0.1', $PORT), 1).close()" 2>/dev/null; then
        break
    fi
    sleep 1
done
docker exec "$NAME" python -c "import socket; socket.create_connection(('127.0.0.1', $PORT), 1).close()" \
    || { docker logs "$NAME"; echo "server did not come up"; exit 1; }

echo "==> write phase"
docker run --rm --network host -v "$ROOT/scripts/smoke.py:/smoke.py:ro" "$IMAGE" python /smoke.py "http://127.0.0.1:$PORT" write

echo "==> restart phase"
docker restart "$NAME" >/dev/null
for _ in $(seq 1 60); do
    if docker exec "$NAME" python -c "import socket; socket.create_connection(('127.0.0.1', $PORT), 1).close()" 2>/dev/null; then
        break
    fi
    sleep 1
done

echo "==> verify phase"
docker run --rm --network host -v "$ROOT/scripts/smoke.py:/smoke.py:ro" "$IMAGE" python /smoke.py "http://127.0.0.1:$PORT" verify

echo "==> graceful stop"
docker stop "$NAME" >/dev/null
CODE="$(docker inspect "$NAME" --format '{{.State.ExitCode}}')"
if [ "$CODE" != "0" ]; then
    docker logs "$NAME"
    echo "container exited with $CODE (expected 0 after SIGINT)"
    exit 1
fi
echo "OK: image $IMAGE passed the smoke test"
