# Python example (with authentication)

A minimal end-to-end example that reads/writes a Milvus collection through the
`milvus-lite` standalone gRPC server, using the official `pymilvus` SDK.

## 1. Start the container

Start the `kennytian/milvus-lite` image with the gRPC port published on
`127.0.0.1:19530`.

**No auth:**

```bash
docker run --rm -p 127.0.0.1:19530:19530 kennytian/milvus-lite
```

**Token auth:**

```bash
docker run --rm -p 127.0.0.1:19530:19530 \
  -e MILVUS_LITE_TOKEN=s3cr3t \
  kennytian/milvus-lite
```

**User/password auth:**

```bash
docker run --rm -p 127.0.0.1:19530:19530 \
  -e MILVUS_LITE_USERNAME=alice \
  -e MILVUS_LITE_PASSWORD=w0nder \
  kennytian/milvus-lite
```

## 2. Install and run

```bash
pip install -r requirements.txt
```

Then run the example with the credentials matching the container:

```bash
# no auth
python demo.py

# token auth
MILVUS_LITE_TOKEN=s3cr3t python demo.py

# user/password auth
MILVUS_LITE_USERNAME=alice MILVUS_LITE_PASSWORD=w0nder python demo.py
```

## Environment variables

| Variable               | Default             | Description                                   |
| ---------------------- | ------------------- | --------------------------------------------- |
| `MILVUS_LITE_ADDR`     | `127.0.0.1:19530`   | gRPC server `host:port`.                      |
| `MILVUS_LITE_TOKEN`    | *(unset)*           | Token / apiKey auth. Takes precedence.        |
| `MILVUS_LITE_USERNAME` | *(unset)*           | Username, paired with `MILVUS_LITE_PASSWORD`. |
| `MILVUS_LITE_PASSWORD` | *(unset)*           | Password for the username form.               |

Auth precedence in the example: **token** > **username + password** > **no
auth**, mirroring the server's own behavior.
