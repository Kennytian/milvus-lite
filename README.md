# Milvus Lite — standalone Docker image

[![Docker Pulls](https://img.shields.io/docker/pulls/kennytian/milvus-lite)](https://hub.docker.com/r/kennytian/milvus-lite)
[![Image Size](https://img.shields.io/docker/image-size/kennytian/milvus-lite/latest)](https://hub.docker.com/r/kennytian/milvus-lite)
[![Platforms](https://img.shields.io/badge/platforms-amd64%20%7C%20arm64-blue)](https://hub.docker.com/r/kennytian/milvus-lite/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Milvus Lite](https://milvus.io/docs/milvus_lite.md) is the lightweight, embedded edition of
[Milvus](https://milvus.io). Upstream ships it as a **Python library only** — there is no official
server. This image wraps it into a **standalone gRPC server** that any Milvus SDK can talk to,
exactly like a remote Milvus instance.

```bash
docker run -d --name milvus-lite \
  -p 127.0.0.1:19530:19530 \
  -v milvus-data:/data \
  --restart unless-stopped \
  kennytian/milvus-lite:latest
```

- **Multi-arch**: `linux/amd64` and `linux/arm64` (native on Apple Silicon, AWS Graviton, ARM servers)
- **Non-root**: runs as uid/gid `10001`, `tini` as PID 1
- **Graceful shutdown**: `SIGINT` drains in-flight RPCs and releases the data-dir lock
- **Persistent**: all state lives under `/data` — mount a volume or a bind mount
- **Self-verifying releases**: every version is smoke-tested (write → restart → read) before it is pushed
- **~470 MB**, no compiler toolchain in the runtime layer
- **Free for everyone**, MIT licensed

---

## Quick start

### docker run

```bash
docker run -d --name milvus-lite \
  -p 127.0.0.1:19530:19530 \
  -v milvus-data:/data \
  --restart unless-stopped \
  kennytian/milvus-lite:latest

docker logs -f milvus-lite
# MilvusLite gRPC server listening on 0.0.0.0:19530 (data_dir='/data')
```

### docker compose

```yaml
services:
  milvus-lite:
    image: kennytian/milvus-lite:latest
    container_name: milvus-lite
    ports:
      - "127.0.0.1:19530:19530"
    volumes:
      - ./data:/data
    restart: unless-stopped
    stop_signal: SIGINT
    deploy:
      resources:
        limits:
          memory: 1G
```

A ready-to-use [`docker-compose.yml`](docker-compose.yml) with `.env` overrides lives in this repo:

```bash
docker compose pull && docker compose up -d
```

## Connect

The server speaks **gRPC on port 19530**. Use PyMilvus 3.x (the same generation as Milvus Lite 3.x):

```bash
pip install "pymilvus==3.0.2"
```

```python
from pymilvus import MilvusClient

client = MilvusClient(uri="http://127.0.0.1:19530")   # a URL, not a local .db path

client.create_collection("demo", dimension=384)
client.insert("demo", [{"id": 1, "vector": [0.1] * 384, "text": "hello"}])
client.load_collection("demo")

print(client.search("demo", data=[[0.1] * 384], limit=1, output_fields=["text"]))
```

Any other official SDK (Go, Java, Node.js, C#) works as well — just point it at `host:19530`.

> `MilvusClient("./x.db")` opens the *embedded* engine in-process. Do not point it at the container's
> data directory: the file lock means only one process can own it. Always use the URL.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `MILVUS_LITE_DATA_DIR` | `/data` | Data directory (a directory, not a single file) |
| `MILVUS_LITE_HOST` | `0.0.0.0` | Listen address **inside** the container |
| `MILVUS_LITE_PORT` | `19530` | gRPC port inside the container |
| `MILVUS_LITE_BIND_ADDR` | `127.0.0.1` (compose only) | Host address the port is published on |
| `MILVUS_LITE_HOST_PORT` | `19530` (compose only) | Host port |

Publish to `0.0.0.0` only on a trusted network — see [Security](#security) below.

## Data, backup and restore

Everything is under `/data` (`collections/`, `databases/`, `LOCK`):

```bash
docker compose stop                 # stop first: the LOCK must be released
tar czf milvus-data-$(date +%F).tgz data/
docker compose start
```

Restore by unpacking the archive back into the same directory. The on-disk format is
**Milvus Lite 3.x**; 2.x `.db` files are not readable by 3.x (the storage engine changed).

Export a collection to BulkWriter JSON (for importing into Milvus Standalone / Zilliz Cloud):

```bash
docker compose run --rm --entrypoint sh milvus-lite -c \
  'milvus-lite dump -d /data -c demo -p /data/export'
```

## Tags and release automation

| Tag | Meaning |
| --- | --- |
| `latest` | newest published version |
| `3`, `3.2` | newest patch of that major / minor line |
| `3.2.2` | exact `milvus-lite` version baked into the image |

A GitHub Actions workflow keeps the image in lockstep with upstream:

- **every push** touching the `Dockerfile`, `entrypoint.sh`, `requirements.txt` or `scripts/` rebuilds and republishes;
- **every day at 03:23 UTC** it asks PyPI for the latest `milvus-lite`. If that is newer than the pin, it builds,
  smoke-tests, pushes the new tags and commits the bump back to `requirements.txt`;
- **already-published versions are skipped**, so the daily check is cheap;
- **manual runs** (`workflow_dispatch`) can rebuild any specific version.

The version lives in exactly one place — [`requirements.txt`](requirements.txt):

```
pymilvus==3.0.2
milvus-lite==3.2.2   # <- change this line to publish 3.2.3
```

Images are built for both architectures, smoke-tested on `linux/amd64`, and published as a
multi-arch manifest list.

## Building locally

```bash
# single architecture, for your machine
docker build -t my/milvus-lite:dev .

# both architectures
docker buildx build --platform linux/amd64,linux/arm64 -t my/milvus-lite:dev .
```

Run the same smoke test the CI uses:

```bash
./scripts/smoke-test.sh my/milvus-lite:dev
```

## Security

Milvus Lite has **no authentication, no users, no RBAC and no TLS** — upstream explicitly warns
against exposing it to an untrusted network. Keep the published port bound to `127.0.0.1`, or put a
proxy with auth/TLS in front of it. The container runs unprivileged, but that does not make the
service safe to expose.

## Limitations (upstream, not the image)

- **One process per data directory** — a file lock protects it, so run a single replica and never share a volume.
- **gRPC only** — no REST endpoints, no Attu-style HTTP API.
- **RPC subset** — unsupported calls return `UNIMPLEMENTED`; schema changes and partition-level load/release are unavailable.
- **Not every index/type** — no `BINARY`/`FLOAT16`/`BFLOAT16`/`INT8` vectors, no `PQ`-family indexes.
- **Concurrent writes to one collection are not safe** — serialize writers.
- HNSW keeps indexes in memory: raise the memory limit as the dataset grows.

Good fit: local development, CI, edge devices, small single-node workloads. For production scale use
Milvus Standalone/Distributed or Zilliz Cloud.

## Maintainer notes

The workflow needs two repository secrets:

| Secret | Value |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub account that owns the repository |
| `DOCKERHUB_TOKEN` | Docker Hub access token with **Read & Write** scope (not the password) |

`GITHUB_TOKEN` with `contents: write` is used to commit automatic version bumps — check
*Settings → Actions → General → Workflow permissions*.

## License

[MIT](LICENSE). Milvus and Milvus Lite are Apache-2.0 licensed projects of the LF AI & Data Foundation;
this image is an unofficial packaging of the upstream package and comes with no warranty.
