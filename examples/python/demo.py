"""Minimal Milvus Lite example with optional authentication.

Connects to a milvus-lite standalone gRPC server and exercises the basic
write/read/search flow against a small collection.

Authentication is driven by environment variables, mirroring the server's
own configuration:

    MILVUS_LITE_TOKEN            optional; token / apiKey form
    MILVUS_LITE_USERNAME         optional; paired with MILVUS_LITE_PASSWORD
    MILVUS_LITE_PASSWORD         optional
    MILVUS_LITE_ADDR             host:port, default 127.0.0.1:19530

Precedence: token wins; otherwise username + password; otherwise no auth.
"""

from __future__ import annotations

import os

from pymilvus import MilvusClient

DIM = 8
COLLECTION = "demo_py"


def build_client() -> MilvusClient:
    addr = os.environ.get("MILVUS_LITE_ADDR", "127.0.0.1:19530")
    uri = f"http://{addr}"

    token = os.environ.get("MILVUS_LITE_TOKEN", "").strip()
    username = os.environ.get("MILVUS_LITE_USERNAME", "").strip()
    password = os.environ.get("MILVUS_LITE_PASSWORD", "")

    if token:
        print(f"Using token auth against {uri}")
        return MilvusClient(uri=uri, token=token)

    if username and password:
        print(f"Using user/pass auth against {uri}")
        return MilvusClient(uri=uri, user=username, password=password)

    print(f"Using no auth against {uri}")
    return MilvusClient(uri=uri)


def main() -> None:
    client = build_client()

    # Create the collection (id + vector auto-schema), tolerating an
    # existing collection from a previous run.
    if client.has_collection(COLLECTION):
        print(f"Collection '{COLLECTION}' already exists, reusing it.")
    else:
        client.create_collection(COLLECTION, dimension=DIM)
        print(f"Created collection '{COLLECTION}' (dim={DIM}).")

    # Insert a couple of rows.
    rows = [
        {"id": 1, "vector": [0.1] * DIM},
        {"id": 2, "vector": [0.9] * DIM},
    ]
    client.insert(COLLECTION, data=rows)
    print(f"Inserted {len(rows)} rows.")

    # Load and search for the nearest neighbor to the first vector.
    client.load_collection(COLLECTION)
    results = client.search(
        COLLECTION,
        data=[[0.1] * DIM],
        limit=1,
        output_fields=["id"],
    )

    for hit in results[0]:
        print(f"Nearest hit: id={hit['id']} distance={hit['distance']:.4f}")


if __name__ == "__main__":
    main()
