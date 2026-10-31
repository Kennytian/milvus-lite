# Milvus Lite as a standalone gRPC server.
# Multi-arch: linux/amd64, linux/arm64 (all dependencies ship wheels, no compiler needed).

########################
# Stage 1: build venv
########################
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} + \
    && find /opt/venv -name '*.pyc' -delete

########################
# Stage 2: runtime
########################
FROM python:3.12-slim-bookworm

# gosu: drop root after fixing /data ownership, keeps PID 1 signalling correct
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu tini \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    MILVUS_LITE_DATA_DIR=/data \
    MILVUS_LITE_HOST=0.0.0.0 \
    MILVUS_LITE_PORT=19530

COPY --from=builder /opt/venv /opt/venv
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
    && groupadd --gid 10001 milvus \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin milvus \
    && mkdir -p /data \
    && chown 10001:10001 /data

VOLUME ["/data"]
WORKDIR /data
EXPOSE 19530

# Milvus Lite handles SIGINT gracefully (drains in-flight RPCs, closes the DB
# and releases the data-dir LOCK); SIGTERM would kill it abruptly.
STOPSIGNAL SIGINT

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["sh", "-c", "python -c \"import os, socket; socket.create_connection(('127.0.0.1', int(os.environ.get('MILVUS_LITE_PORT', 19530))), 3).close()\""]

ENTRYPOINT ["tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["milvus-lite", "server"]
