# run_queries.py
"""
Console runner — executes all 5 mandatory queries against PostgreSQL,
MongoDB, and Neo4j, printing results side-by-side in the terminal.

Usage
-----
    python run_queries.py                    # runs all queries
    python run_queries.py --login user_0001  # override test login
    python run_queries.py --city  Київ       # override test city
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date
from typing import Any

from tabulate import tabulate

import db_postgres
import db_mongo
import db_neo4j

# ── Serialisation helpers ───────────────────────────────────────────

def _json_default(obj: Any) -> str:
    if isinstance(obj, date):
        return obj.isoformat()
    return str(obj)


def _pretty(obj: Any, max_width: int = 100) -> str:
    """Return a human-readable string for terminal display."""
    if obj is None:
        return "(not found)"
    if isinstance(obj, dict):
        return json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default)
    if isinstance(obj, list) and len(obj) == 0:
        return "(empty list)"
    if isinstance(obj, list) and isinstance(obj[0], str):
        return ", ".join(obj)
    if isinstance(obj, list) and isinstance(obj[0], dict):
        # Show as a table
        if len(obj) > 40:
            rows = obj[:20] + [{"...": f"… and {len(obj) - 40} more …"}] + obj[-20:]
        else:
            rows = obj
        return tabulate(rows, headers="keys", tablefmt="simple")
    return str(obj)


import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Engine wrapper ──────────────────────────────────────────────────

class Engine:
    def __init__(self, name: str, module):
        self.name = name
        self.m = module


ENGINES = [
    Engine("PostgreSQL", db_postgres),
    Engine("MongoDB",    db_mongo),
    Engine("Neo4j",      db_neo4j),
]


def run_query(label: str, engines: list[Engine], func_name: str, *args):
    """Execute ``func_name(*args)`` on each engine and print results."""
    print(f"\n{'-' * 72}")
    print(f"  {label}")
    if args:
        print(f"  Arguments: {args}")
    print(f"{'-' * 72}")

    for eng in engines:
        fn = getattr(eng.m, func_name)
        t0 = time.perf_counter()
        result = fn(*args)
        elapsed = time.perf_counter() - t0

        print(f"\n  [+] {eng.name}  ({elapsed*1000:.1f} ms)")
        print(f"  {'-' * 60}")
        output = _pretty(result)
        # Indent every line for readability
        for line in output.split("\n"):
            print(f"    {line}")


# ── Main ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="HR Resume DB — Query Runner")
    parser.add_argument("--login", default="user_0001",
                        help="User login for Q1 (default: user_0001)")
    parser.add_argument("--city",  default="Kyiv",
                        help="City name for Q4 (default: Kyiv)")
    opts = parser.parse_args()

    print("=" * 72)
    print("  HR Resume Database — Query Comparison Runner")
    print("=" * 72)

    # Q1: Resume by login
    run_query(
        f"Q1 — Full resume for user '{opts.login}' / Повне резюме користувача",
        ENGINES, "q1_resume_by_login", opts.login,
    )

    # Q2: All unique hobbies
    run_query(
        "Q2 — All unique hobbies across all resumes / Усі унікальні хобі",
        ENGINES, "q2_all_hobbies",
    )

    # Q3: All unique cities
    run_query(
        "Q3 — All unique cities across all resumes / Усі унікальні міста",
        ENGINES, "q3_all_cities",
    )

    # Q4: Hobbies by city
    run_query(
        f"Q4 — Hobbies of candidates in '{opts.city}' / Хобі здобувачів з міста",
        ENGINES, "q4_hobbies_by_city", opts.city,
    )

    # Q5: Shared workplace
    run_query(
        "Q5 — Pairs of candidates who worked at the same company / Спільний заклад роботи",
        ENGINES, "q5_shared_workplace",
    )

    print(f"\n{'=' * 72}")
    print("  Done — all queries executed successfully.")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()

