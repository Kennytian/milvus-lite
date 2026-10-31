"""Milvus Lite gRPC server entry point with optional authentication.

This is a thin wrapper around milvus-lite's own gRPC adapter. It exists for one
reason: milvus-lite's ``run_server`` does not expose a way to inject a
``grpc.ServerInterceptor``, so we assemble the server ourselves (the assembly
is ~15 lines) and add the auth interceptor from ``auth.py`` before serving.

Configuration is taken from the environment (see the Dockerfile for defaults):

    MILVUS_LITE_DATA_DIR     data directory (default /data)
    MILVUS_LITE_HOST         bind host (default 0.0.0.0)
    MILVUS_LITE_PORT         bind port (default 19530)
    MILVUS_LITE_MAX_WORKERS  gRPC thread-pool size (default 10)
    MILVUS_LITE_TOKEN / MILVUS_LITE_USERNAME / MILVUS_LITE_PASSWORD  -> auth

When no auth variable is set, the server behaves exactly like
``milvus-lite server``.
"""

from __future__ import annotations

import os
from concurrent import futures

import grpc
from pymilvus.grpc_gen import milvus_pb2_grpc

from milvus_lite.adapter.grpc.servicer import MilvusServicer
from milvus_lite.db import MilvusLite

from auth import build_auth_interceptor

_MAX_MESSAGE_SIZE = 256 * 1024 * 1024  # 256 MB, matching Milvus Standalone


def main() -> None:
    data_dir = os.environ.get("MILVUS_LITE_DATA_DIR", "/data")
    host = os.environ.get("MILVUS_LITE_HOST", "0.0.0.0")
    port = int(os.environ.get("MILVUS_LITE_PORT", "19530"))
    max_workers = int(os.environ.get("MILVUS_LITE_MAX_WORKERS", "10"))

    interceptor = build_auth_interceptor()
    interceptors = [interceptor] if interceptor is not None else None

    db = MilvusLite(data_dir)
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ("grpc.max_receive_message_length", _MAX_MESSAGE_SIZE),
            ("grpc.max_send_message_length", _MAX_MESSAGE_SIZE),
        ],
        interceptors=interceptors,
    )
    servicer = MilvusServicer(db)
    milvus_pb2_grpc.add_MilvusServiceServicer_to_server(servicer, server)

    addr = f"{host}:{port}"
    server.add_insecure_port(addr)
    server.start()
    print(
        f"MilvusLite gRPC server listening on {addr} "
        f"(data_dir={data_dir!r}, auth={'enabled' if interceptor else 'disabled'})"
    )

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop(grace=5)
        db.close()


if __name__ == "__main__":
    main()
