#!/usr/bin/env python
"""End-to-end smoke test for the containerized Milvus Lite server.

Usage:
    python smoke.py <uri> [write|verify]

    write   create a collection, insert 5 rows, search, check row count
    verify  the data written by a previous `write` survived a restart
"""

import random
import sys

from pymilvus import MilvusClient

COLLECTION = "smoke_docs"
DIM = 8
ROWS = 5


def fail(msg):
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main():
    uri = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19530"
    phase = sys.argv[2] if len(sys.argv) > 2 else "write"

    client = MilvusClient(uri=uri)
    print(f"connected: {uri} (phase={phase})")

    if phase == "write":
        if client.has_collection(COLLECTION):
            client.drop_collection(COLLECTION)
        client.create_collection(
            collection_name=COLLECTION, dimension=DIM, metric_type="COSINE", auto_id=False
        )
        rows = [
            {"id": i, "vector": [random.random() for _ in range(DIM)], "text": f"doc-{i}"}
            for i in range(ROWS)
        ]
        client.insert(collection_name=COLLECTION, data=rows)
    else:
        if not client.has_collection(COLLECTION):
            fail(f"collection {COLLECTION} disappeared after restart")

    client.load_collection(collection_name=COLLECTION)

    stats = client.get_collection_stats(collection_name=COLLECTION)
    count = stats["row_count"]
    print(f"row_count={count}")
    if count < ROWS:
        fail(f"expected >= {ROWS} rows, got {count}")

    vector = client.query(collection_name=COLLECTION, filter="id == 0", output_fields=["vector"])[0]["vector"]
    hits = client.search(collection_name=COLLECTION, data=[vector], limit=3, output_fields=["text"])
    top = hits[0][0]
    print(f"search top hit: {top}")
    if top["id"] != 0 or top["distance"] < 0.99:
        fail("self-similarity search did not return id=0 as the closest hit")

    client.close()
    print(f"OK ({phase})")


if __name__ == "__main__":
    main()
