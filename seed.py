# seed.py
"""
Unified seeding script — generates the dataset once and loads it into
PostgreSQL, MongoDB, and Neo4j in parallel-safe sequence.

Usage
-----
    docker compose up -d          # start all three databases
    pip install -r requirements.txt
    python seed.py                # populate all three databases
"""
from __future__ import annotations

import sys
import time

from datagen import generate_candidates
import db_postgres
import db_mongo
import db_neo4j


def main() -> None:
    print("=" * 64)
    print("  HR Resume Database — Unified Seeder")
    print("=" * 64)

    print("\n▸ Generating candidate dataset …")
    data = generate_candidates()
    n = len(data["candidates"])
    print(f"  ✓ {n} candidates generated")
    print(f"    Cities: {len(data['cities'])}  |  Hobbies: {len(data['hobbies'])}  "
          f"|  Companies: {len(data['companies'])}  |  Universities: {len(data['universities'])}")

    # ── PostgreSQL ──────────────────────────────────────────────────
    print("\n▸ Seeding PostgreSQL …", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        db_postgres.seed(data)
        print(f"✓  ({time.perf_counter() - t0:.2f}s)")
    except Exception as e:
        print(f"✗  {e}")
        sys.exit(1)

    # ── MongoDB ─────────────────────────────────────────────────────
    print("▸ Seeding MongoDB …", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        db_mongo.seed(data)
        print(f"✓  ({time.perf_counter() - t0:.2f}s)")
    except Exception as e:
        print(f"✗  {e}")
        sys.exit(1)

    # ── Neo4j ───────────────────────────────────────────────────────
    print("▸ Seeding Neo4j …", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        db_neo4j.seed(data)
        print(f"✓  ({time.perf_counter() - t0:.2f}s)")
    except Exception as e:
        print(f"✗  {e}")
        sys.exit(1)

    print("\n" + "=" * 64)
    print("  All three databases seeded successfully!")
    print("=" * 64)


if __name__ == "__main__":
    main()
