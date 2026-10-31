"""gRPC authentication for the Milvus Lite server.

Milvus' official SDKs all transmit credentials the same way: they put a bare
base64 string into the gRPC ``authorization`` metadata key (no ``Bearer `` /
``Basic `` prefix). The payload is either the API token itself, or
``username:password``:

    token              -> base64(token)
    username + password -> base64("username:password")

This module turns that convention into a single ``grpc.ServerInterceptor`` that
rejects every RPC whose ``authorization`` metadata does not decode to one of the
credentials the operator configured. It is deliberately tiny: it only gates
entry ("door check"), it never re-implements Milvus' RBAC.

Credentials are read from the environment at process start:

    MILVUS_LITE_TOKEN                 optional; accepts the ``token``/``apiKey``
                                      form (any of the official SDKs)
    MILVUS_LITE_USERNAME              optional; paired with MILVUS_LITE_PASSWORD
    MILVUS_LITE_PASSWORD              optional; accepts the ``username:password`` form

If none of the three is set, no interceptor is installed and the server behaves
exactly as before (no authentication) — backwards compatible.
"""

from __future__ import annotations

import base64
import hmac
import os
from typing import Iterable, Optional, Set

import grpc

_UNAUTHENTICATED = grpc.StatusCode.UNAUTHENTICATED


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def build_auth_interceptor() -> Optional["grpc.ServerInterceptor"]:
    """Return an auth interceptor, or ``None`` when auth is not configured."""
    token = os.environ.get("MILVUS_LITE_TOKEN", "").strip()
    username = os.environ.get("MILVUS_LITE_USERNAME", "").strip()
    password = os.environ.get("MILVUS_LITE_PASSWORD", "")

    expected: Set[str] = set()
    if token:
        expected.add(_b64(token))
    if username and password:
        expected.add(_b64(f"{username}:{password}"))

    if not expected:
        return None
    return _AuthInterceptor(expected)


class _AuthInterceptor(grpc.ServerInterceptor):
    def __init__(self, expected: Iterable[str]) -> None:
        self._expected = tuple(expected)

    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata or ())
        auth = metadata.get("authorization")
        # gRPC surfaces ASCII metadata values as str; compare as str, in
        # constant time, against every configured credential.
        if auth is not None and isinstance(auth, str) and any(
            hmac.compare_digest(auth, expected) for expected in self._expected
        ):
            return continuation(handler_call_details)
        return _abort_handler()


class _AbortHandler:
    """RPC handler that aborts with UNAUTHENTICATED for any method shape."""

    request_streaming = False
    response_streaming = False
    request_deserializer = None
    response_serializer = None

    def _abort(self, request, context):
        context.abort(_UNAUTHENTICATED, "invalid or missing authorization")

    def unary_unary(self, request, context):
        self._abort(request, context)

    def unary_stream(self, request, context):
        self._abort(request, context)

    def stream_unary(self, request_iterator, context):
        self._abort(request_iterator, context)

    def stream_stream(self, request_iterator, context):
        self._abort(request_iterator, context)


def _abort_handler() -> _AbortHandler:
    return _AbortHandler()
