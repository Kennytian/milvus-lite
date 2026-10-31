# Milvus Lite — standalone Docker image

[![Docker Pulls](https://img.shields.io/docker/pulls/kennytian/milvus-lite)](https://hub.docker.com/r/kennytian/milvus-lite)
[![Image Size](https://img.shields.io/docker/image-size/kennytian/milvus-lite/latest)](https://hub.docker.com/r/kennytian/milvus-lite)
[![Platforms](https://img.shields.io/badge/platforms-amd64%20%7C%20arm64-blue)](https://hub.docker.com/r/kennytian/milvus-lite/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/Kennytian/milvus-lite/blob/master/LICENSE)
[![Source](https://img.shields.io/badge/source-GitHub-181717?logo=github)](https://github.com/Kennytian/milvus-lite)

[Milvus Lite](https://milvus.io/docs/milvus_lite.md) is the lightweight, embedded edition of
[Milvus](https://milvus.io). Upstream ships it as a **Python library only** — there is no official
server. This image wraps it into a **standalone gRPC server** that any Milvus SDK can talk to,
exactly like a remote Milvus instance.

**Source code, issues and the release pipeline:** <https://github.com/Kennytian/milvus-lite>

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

A ready-to-use [`docker-compose.yml`](https://github.com/Kennytian/milvus-lite/blob/master/docker-compose.yml) with `.env` overrides lives in the repository:

```bash
docker compose pull && docker compose up -d
```

## Connect

The server speaks **gRPC on port 19530**. The official
[Node.js SDK](https://github.com/milvus-io/milvus-sdk-node) (`@zilliz/milvus2-sdk-node` 3.x — the
generation that matches Milvus 3.x) talks to it out of the box:

```bash
npm install @zilliz/milvus2-sdk-node@3
```

```js
// demo.mjs — run with: node demo.mjs
import { MilvusClient, DataType, MetricType } from '@zilliz/milvus2-sdk-node';

const client = new MilvusClient({ address: '127.0.0.1:19530' });
await client.connectPromise;

await client.createCollection({
  collection_name: 'demo',
  fields: [
    { name: 'id', data_type: DataType.Int64, is_primary_key: true, autoID: true },
    { name: 'text', data_type: DataType.VarChar, max_length: 512 },
    { name: 'vector', data_type: DataType.FloatVector, dim: 384 },
  ],
  index_params: [
    {
      field_name: 'vector',
      index_type: 'HNSW',
      metric_type: MetricType.COSINE,
      params: { M: 16, efConstruction: 256 },
    },
  ],
});

// Must be loaded before search/query.
await client.loadCollectionSync({ collection_name: 'demo' });

await client.insert({
  collection_name: 'demo',
  data: [
    { vector: Array.from({ length: 384 }, (_, i) => (i % 10) / 10), text: 'hello world' },
    { vector: Array.from({ length: 384 }, (_, i) => ((i + 5) % 10) / 10), text: 'another doc' },
  ],
});

const res = await client.search({
  collection_name: 'demo',
  data: [Array.from({ length: 384 }, (_, i) => (i % 10) / 10)],
  limit: 2,
  consistency_level: 'Strong', // see the rows inserted a moment ago
  output_fields: ['text'],
});
console.log(res.results); // [ { score: 0.999…, text: 'hello world' }, … ]

await client.closeConnection();
```

Any official SDK works — Python, Go, Java, C# — just point it at `host:19530`.

> The Node.js SDK has no embedded mode — it always needs a reachable server, which is exactly what
> this image provides. The Python SDK does have one (`MilvusClient("./x.db")`), but never point it at
> the container's data directory: the file lock allows a single process only. Use the URL.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `MILVUS_LITE_DATA_DIR` | `/data` | Data directory (a directory, not a single file) |
| `MILVUS_LITE_HOST` | `0.0.0.0` | Listen address **inside** the container |
| `MILVUS_LITE_PORT` | `19530` | gRPC port inside the container |
| `MILVUS_LITE_BIND_ADDR` | `127.0.0.1` (compose only) | Host address the port is published on |
| `MILVUS_LITE_HOST_PORT` | `19530` (compose only) | Host port |
| `MILVUS_LITE_TOKEN` | _(empty)_ | Optional: accept a single API token |
| `MILVUS_LITE_USERNAME` | _(empty)_ | Optional: accept `username:password` (paired with `MILVUS_LITE_PASSWORD`) |
| `MILVUS_LITE_PASSWORD` | _(empty)_ | Optional: paired with `MILVUS_LITE_USERNAME` |

Publish to `0.0.0.0` only on a trusted network — see **Security** below.

## Authentication

Milvus Lite itself ships no auth, so this image adds a thin, optional **gate** in front of the gRPC
server. When at least one of `MILVUS_LITE_TOKEN` / `MILVUS_LITE_USERNAME`+`MILVUS_LITE_PASSWORD` is
set, every RPC must carry matching credentials in the `authorization` metadata — exactly what the
official SDKs already send. Leave all three empty and the server is unauthenticated, as before.

```bash
# token form
docker run -e MILVUS_LITE_TOKEN=s3cr3t -p 127.0.0.1:19530:19530 kennytian/milvus-lite

# username + password form
docker run -e MILVUS_LITE_USERNAME=alice -e MILVUS_LITE_PASSWORD=w0nder -p 127.0.0.1:19530:19530 kennytian/milvus-lite
```

Clients pass the same value through their normal SDK auth field — no custom code:

```python
# token
MilvusClient(uri, token="s3cr3t")
# username + password
MilvusClient(uri, user="alice", password="w0nder")
```

```js
new MilvusClient({ address: '127.0.0.1:19530', token: 's3cr3t' });
```

What this is **not**: it is a single shared credential, not per-user RBAC, and it does not add TLS.
It only keeps the port from being trivially open to anyone who can reach it. Pair it with a TLS
terminating proxy (or a private network) when the service leaves the loopback.

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

The version lives in exactly one place — [`requirements.txt`](https://github.com/Kennytian/milvus-lite/blob/master/requirements.txt):

```
pymilvus==3.0.2      # bumped automatically to the newest 3.x on every build
milvus-lite==3.2.2   # <- change this line to publish 3.2.3
```

**You never have to watch `pymilvus`.** Whenever the workflow builds a new milvus-lite version it
also resolves the newest `pymilvus` release of the same major from PyPI, installs that, and commits
the pin back to `requirements.txt`. Already published tags are never rebuilt, so a tag keeps
pointing at the exact bytes it was published with.

If you want a `pymilvus`-only refresh between milvus-lite releases, run the workflow manually
(*Actions → Release → Run workflow*) — a manual run always rebuilds, even for an existing tag.

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

Milvus Lite has **no users, no RBAC and no TLS** — upstream explicitly warns against exposing it to
an untrusted network. This image adds an optional single-credential gate (see **Authentication**),
but that is not a substitute for TLS or per-user access control. Keep the published port bound to
`127.0.0.1`, or put a TLS-terminating proxy in front of it. The container runs unprivileged, but that
does not make the service safe to expose.

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
| `DOCKERHUB_TOKEN` | Docker Hub access token with **Read, Write, Delete** scope (not the password) |

The token needs the delete permission only because the workflow also keeps the Docker Hub
description in sync with `README.md` (Account settings → Personal access tokens).

`GITHUB_TOKEN` with `contents: write` is used to commit automatic version bumps — check
*Settings → Actions → General → Workflow permissions*.

## License

[MIT](https://github.com/Kennytian/milvus-lite/blob/master/LICENSE). Source, issues and the release pipeline live at
<https://github.com/Kennytian/milvus-lite>.

Milvus and Milvus Lite are Apache-2.0 licensed projects of the LF AI & Data Foundation;
this image is an unofficial packaging of the upstream package and comes with no warranty.
