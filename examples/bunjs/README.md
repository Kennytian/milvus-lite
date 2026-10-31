# Bun.js example — Milvus Lite with authentication

A minimal, self-contained [Bun.js](https://bun.sh) example that connects to the
[`kennytian/milvus-lite`](https://hub.docker.com/r/kennytian/milvus-lite) Docker image,
creates a collection, inserts rows, loads it, and runs a vector search — with the
SDK's built-in authentication.

The official [Node.js SDK](https://github.com/milvus-io/milvus-sdk-node)
(`@zilliz/milvus2-sdk-node` 3.x) is used; Bun installs npm packages directly.

## 1. Start the container

Start `kennytian/milvus-lite` with **one** of these auth configurations (leave all
three auth variables empty to run unauthenticated):

```bash
# token form
docker run -d --name milvus-lite \
  -e MILVUS_LITE_TOKEN=s3cr3t \
  -p 127.0.0.1:19530:19530 \
  kennytian/milvus-lite

# username + password form
docker run -d --name milvus-lite \
  -e MILVUS_LITE_USERNAME=alice \
  -e MILVUS_LITE_PASSWORD=w0nder \
  -p 127.0.0.1:19530:19530 \
  kennytian/milvus-lite
```

## 2. Install and run

```bash
cd examples/bunjs
bun install
bun run demo.ts
```

The demo reads the server address and credentials from the environment:

| Variable | Default | Description |
| --- | --- | --- |
| `MILVUS_LITE_ADDR` | `127.0.0.1:19530` | Server `host:port`. |
| `MILVUS_LITE_TOKEN` | _(empty)_ | API token (`token` form; takes precedence). |
| `MILVUS_LITE_USERNAME` | _(empty)_ | Username (paired with `MILVUS_LITE_PASSWORD`). |
| `MILVUS_LITE_PASSWORD` | _(empty)_ | Password (paired with `MILVUS_LITE_USERNAME`). |

Match the values to how you started the container:

```bash
# token form
MILVUS_LITE_TOKEN=s3cr3t bun run demo.ts

# username + password form
MILVUS_LITE_USERNAME=alice MILVUS_LITE_PASSWORD=w0nder bun run demo.ts

# no auth
bun run demo.ts
```

## What it does

1. Reads auth config from the environment (token wins over username/password).
2. Connects with the appropriate credentials.
3. Creates a `demo` collection (Int64 `id` with `autoID`, `text` VarChar, `vector`
   FloatVector of dim 8) — idempotent via `hasCollection`.
4. Inserts two rows and loads the collection.
5. Runs a search and prints each hit's `score` and `text`.
6. Closes the connection.
