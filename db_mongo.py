# db_mongo.py
"""
MongoDB layer — collection setup, seeding, and all 5 queries.

Schema design notes
-------------------
* Single denormalized collection ``resumes``.
* ``user`` sub-document embeds login + password_hash (1:1).
* ``city`` stored as a plain string (1:N modelled implicitly).
* ``hobbies`` is an embedded array of strings (M:N via embedding).
* ``experience`` is an array of sub-documents with company, position,
  start_date, end_date  (M:N with attributes via embedding).
* ``education`` is either ``null`` / absent or a sub-document
  ``{university, degree, graduation_year}``.
*
* Indexes created on ``user.login`` (unique), ``city``, ``hobbies``,
  and ``experience.company``.
"""
from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection

import config

# ── helpers ─────────────────────────────────────────────────────────

def _client() -> MongoClient:
    return MongoClient(
        host=config.MONGO_HOST,
        port=config.MONGO_PORT,
        username=config.MONGO_USER,
        password=config.MONGO_PASSWORD,
        authSource="admin",
    )


def _col() -> Collection:
    client = _client()
    return client[config.MONGO_DBNAME]["resumes"]


# ── Seed ────────────────────────────────────────────────────────────

def seed(data: dict[str, Any]) -> None:
    """Drop collection, re-create indexes, bulk-insert all documents."""
    client = _client()
    db = client[config.MONGO_DBNAME]
    db.drop_collection("resumes")
    col = db["resumes"]

    docs: list[dict] = []
    for c in data["candidates"]:
        doc: dict[str, Any] = {
            "user": {
                "login": c["login"],
                "password_hash": c["password_hash"],
            },
            "full_name":  c["full_name"],
            "birth_date": c["birth_date"].isoformat(),
            "summary":    c["summary"],
            "city":       c["city"],
            "hobbies":    c["hobbies"],
            "experience": [
                {
                    "company":    e["company"],
                    "position":   e["position"],
                    "start_date": e["start_date"].isoformat(),
                    "end_date":   e["end_date"].isoformat() if e["end_date"] else None,
                }
                for e in c["experience"]
            ],
        }
        doc["education"] = c["education"]

        docs.append(doc)

    col.insert_many(docs)

    # Indexes
    col.create_index("user.login", unique=True)
    col.create_index("city")
    col.create_index("hobbies")
    col.create_index("experience.company")

    client.close()


# ── Queries ─────────────────────────────────────────────────────────

def q1_resume_by_login(login: str) -> dict | None:
    """Q1: Full resume for a specific user login."""
    col = _col()
    doc = col.find_one(
        {"user.login": login},
        {"_id": 0},
    )
    return doc


def q2_all_hobbies() -> list[str]:
    """Q2: All unique hobbies across all resumes."""
    col = _col()
    return sorted(col.distinct("hobbies"))


def q3_all_cities() -> list[str]:
    """Q3: All unique cities across all resumes."""
    col = _col()
    return sorted(col.distinct("city"))


def q4_hobbies_by_city(city: str) -> list[str]:
    """Q4: All hobbies of candidates living in a given city."""
    col = _col()
    pipeline = [
        {"$match": {"city": city}},
        {"$unwind": "$hobbies"},
        {"$group": {"_id": "$hobbies"}},
        {"$sort": {"_id": 1}},
    ]
    return [doc["_id"] for doc in col.aggregate(pipeline)]


def q5_shared_workplace() -> list[dict]:
    """
    Q5: Pairs of candidates who worked at the same company.

    Aggregation pipeline (matches MongoDB mongosh query from report):
      1. $unwind: unwind the experience array.
      2. $group: cluster candidates by company using $addToSet.
      3. $match: keep only companies with ≥ 2 candidates ("candidates.1": {$exists: true}).
      4. $sort: sort by company name.
    
    Pairs are then formed combinatorially from candidate clusters
    to produce the exact same pairs structure as PostgreSQL and Neo4j.
    """
    col = _col()
    pipeline = [
        {"$unwind": "$experience"},
        {
            "$group": {
                "_id": "$experience.company",
                "candidates": {
                    "$addToSet": {
                        "login": "$user.login",
                        "full_name": "$full_name",
                    }
                },
            }
        },
        {"$match": {"candidates.1": {"$exists": True}}},
        {"$sort": {"_id": 1}},
    ]

    results: list[dict] = []
    for doc in col.aggregate(pipeline):
        company = doc["_id"]
        cands = sorted(doc["candidates"], key=lambda x: x["login"])
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                results.append({
                    "company":     company,
                    "candidate_1": cands[i]["full_name"],
                    "candidate_2": cands[j]["full_name"],
                })

    results.sort(key=lambda r: (r["company"], r["candidate_1"], r["candidate_2"]))
    return results

