# db_neo4j.py
"""
Neo4j layer — graph creation, seeding, and all 5 queries.

Graph design notes
------------------
Nodes
  (:User   {login, password_hash})
  (:Resume {login, full_name, birth_date, summary})
  (:City   {name})
  (:Hobby  {name})
  (:Company{name})
  (:University {name})

Relationships
  (:User)-[:OWNS]->(:Resume)                                     — 1:1
  (:Resume)-[:LIVES_IN]->(:City)                                  — N:1
  (:Resume)-[:ENJOYS]->(:Hobby)                                   — M:N
  (:Resume)-[:WORKED_AT {position, start_date, end_date}]->(:Company)   — M:N + attrs
  (:Resume)-[:STUDIED_AT {degree, graduation_year}]->(:University)      — M:N (0, 1, or 2 degrees)

Constraints
  UNIQUE on User.login, Resume.login, City.name, Hobby.name, Company.name, University.name
"""
from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

import config

# ── helpers ─────────────────────────────────────────────────────────

def _driver():
    return GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
    )


# ── Seed ────────────────────────────────────────────────────

_CONSTRAINTS = """
CREATE CONSTRAINT user_login   IF NOT EXISTS FOR (u:User)       REQUIRE u.login IS UNIQUE;
CREATE CONSTRAINT resume_login IF NOT EXISTS FOR (r:Resume)     REQUIRE r.login IS UNIQUE;
CREATE CONSTRAINT city_name    IF NOT EXISTS FOR (c:City)       REQUIRE c.name  IS UNIQUE;
CREATE CONSTRAINT hobby_name   IF NOT EXISTS FOR (h:Hobby)      REQUIRE h.name  IS UNIQUE;
CREATE CONSTRAINT company_name IF NOT EXISTS FOR (co:Company)   REQUIRE co.name IS UNIQUE;
CREATE CONSTRAINT uni_name     IF NOT EXISTS FOR (un:University) REQUIRE un.name IS UNIQUE;
"""


def seed(data: dict[str, Any]) -> None:
    """Wipe existing graph, create constraints, and batch-insert all data."""
    driver = _driver()
    with driver.session() as s:
        # Clean slate
        s.run("MATCH (n) DETACH DELETE n")

        # Constraints (one statement per call)
        for stmt in _CONSTRAINTS.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                s.run(stmt)

        # Reference nodes ─────────────────────────────────────────────
        for city in data["cities"]:
            s.run("MERGE (:City {name: $name})", name=city)
        for hobby in data["hobbies"]:
            s.run("MERGE (:Hobby {name: $name})", name=hobby)
        for company in data["companies"]:
            s.run("MERGE (:Company {name: $name})", name=company)
        for uni in data["universities"]:
            s.run("MERGE (:University {name: $name})", name=uni)

        # Candidates ─── batch in chunks for speed ────────────────────
        _BATCH = 50
        candidates = data["candidates"]
        for start in range(0, len(candidates), _BATCH):
            chunk = candidates[start : start + _BATCH]
            _seed_chunk(s, chunk)

    driver.close()


def _seed_chunk(session, chunk: list[dict]) -> None:
    """Insert a chunk of candidates with all relationships."""
    for c in chunk:
        # User + Resume + LIVES_IN
        params: dict[str, Any] = {
            "login":         c["login"],
            "password_hash": c["password_hash"],
            "full_name":     c["full_name"],
            "birth_date":    c["birth_date"].isoformat(),
            "summary":       c["summary"],
            "city":          c["city"],
        }
        session.run(
            """
            CREATE (u:User {login: $login, password_hash: $password_hash})
            CREATE (r:Resume {login: $login,
                              full_name: $full_name,
                              birth_date: $birth_date,
                              summary: $summary})
            CREATE (u)-[:OWNS]->(r)
            WITH r
            MATCH (ci:City {name: $city})
            CREATE (r)-[:LIVES_IN]->(ci)
            """,
            **params,
        )

        # Hobbies
        for h in c["hobbies"]:
            session.run(
                """
                MATCH (r:Resume {login: $login})
                MATCH (h:Hobby {name: $hobby})
                MERGE (r)-[:ENJOYS]->(h)
                """,
                login=c["login"],
                hobby=h,
            )

        # Education (0, 1, or 2 degrees)
        for edu in c["education"]:
            session.run(
                """
                MATCH (r:Resume {login: $login})
                MATCH (un:University {name: $university})
                CREATE (r)-[:STUDIED_AT {degree: $degree,
                                          graduation_year: $grad_year}]->(un)
                """,
                login=c["login"],
                university=edu["university"],
                degree=edu["degree"],
                grad_year=edu["graduation_year"],
            )

        # Experience
        for e in c["experience"]:
            session.run(
                """
                MATCH (r:Resume {login: $login})
                MATCH (co:Company {name: $company})
                CREATE (r)-[:WORKED_AT {position: $position,
                                         start_date: $start_date,
                                         end_date: $end_date}]->(co)
                """,
                login=c["login"],
                company=e["company"],
                position=e["position"],
                start_date=e["start_date"].isoformat(),
                end_date=e["end_date"].isoformat() if e["end_date"] else None,
            )


# ── Queries ─────────────────────────────────────────────────────────

def q1_resume_by_login(login: str) -> dict | None:
    """Q1: Full resume for a specific user login."""
    driver = _driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (u:User {login: $login})-[:OWNS]->(r:Resume)-[:LIVES_IN]->(c:City)
            RETURN u.login      AS login,
                   r.full_name  AS full_name,
                   r.birth_date AS birth_date,
                   r.summary    AS summary,
                   c.name       AS city
            """,
            login=login,
        )
        record = result.single()
        if record is None:
            driver.close()
            return None

        resume = dict(record)

        # Education
        edu_result = s.run(
            """
            MATCH (u:User {login: $login})-[:OWNS]->(r:Resume)-[st:STUDIED_AT]->(un:University)
            RETURN un.name            AS university,
                   st.degree          AS degree,
                   st.graduation_year AS graduation_year
            ORDER BY st.graduation_year
            """,
            login=login,
        )
        resume["education"] = [dict(rec) for rec in edu_result]

        # Hobbies
        hobbies_result = s.run(
            """
            MATCH (u:User {login: $login})-[:OWNS]->(r:Resume)-[:ENJOYS]->(h:Hobby)
            RETURN h.name AS hobby ORDER BY h.name
            """,
            login=login,
        )
        resume["hobbies"] = [rec["hobby"] for rec in hobbies_result]

        # Experience
        exp_result = s.run(
            """
            MATCH (u:User {login: $login})-[:OWNS]->(r:Resume)-[w:WORKED_AT]->(co:Company)
            RETURN co.name    AS company,
                   w.position   AS position,
                   w.start_date AS start_date,
                   w.end_date   AS end_date
            ORDER BY w.start_date
            """,
            login=login,
        )
        resume["experience"] = [dict(rec) for rec in exp_result]

    driver.close()
    return resume


def q2_all_hobbies() -> list[str]:
    """Q2: All unique hobbies across all resumes."""
    driver = _driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (:Resume)-[:ENJOYS]->(h:Hobby)
            RETURN DISTINCT h.name AS hobby
            ORDER BY hobby
            """
        )
        hobbies = [rec["hobby"] for rec in result]
    driver.close()
    return hobbies


def q3_all_cities() -> list[str]:
    """Q3: All unique cities across all resumes."""
    driver = _driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (:Resume)-[:LIVES_IN]->(c:City)
            RETURN DISTINCT c.name AS city
            ORDER BY city
            """
        )
        cities = [rec["city"] for rec in result]
    driver.close()
    return cities


def q4_hobbies_by_city(city: str) -> list[str]:
    """Q4: All hobbies of candidates living in a given city."""
    driver = _driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (r:Resume)-[:LIVES_IN]->(c:City {name: $city})
            MATCH (r)-[:ENJOYS]->(h:Hobby)
            RETURN DISTINCT h.name AS hobby
            ORDER BY hobby
            """,
            city=city,
        )
        hobbies = [rec["hobby"] for rec in result]
    driver.close()
    return hobbies


def q5_shared_workplace() -> list[dict]:
    """
    Q5: Pairs of candidates who worked at the same company.

    Cypher naturally expresses this as a pattern match —
    two resumes that both have a WORKED_AT edge to the same Company node.
    The inequality filter r1.login < r2.login prevents duplicates.
    """
    driver = _driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (r1:Resume)-[:WORKED_AT]->(co:Company)<-[:WORKED_AT]-(r2:Resume)
            WHERE r1.login < r2.login
            RETURN co.name     AS company,
                   r1.full_name AS candidate_1,
                   r2.full_name AS candidate_2
            ORDER BY company, candidate_1, candidate_2
            """
        )
        pairs = [dict(rec) for rec in result]
    driver.close()
    return pairs
