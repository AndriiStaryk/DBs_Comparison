# db_postgres.py
"""
PostgreSQL layer — schema creation, seeding, and all 5 queries.

Schema design notes
-------------------
* ``users`` ↔ ``resumes``: 1-to-1 via ``UNIQUE`` FK on ``resumes.user_id``.
* ``cities`` → ``resumes``: 1-to-many (``resumes.city_id`` FK).
* ``educations``: 1-to-many from ``resumes``, N:1 to ``universities``.
  Fully normalized table supporting 0, 1 (Bachelor), or 2 (Bachelor + Master)
  degrees per candidate.
* ``resume_hobbies``: Classic M:N junction table.
* ``experience``: M:N junction *with attributes* (position, dates) between
  ``resumes`` and ``companies``.
* Unique constraint ``(resume_id, company_id)`` on ``experience`` prevents
  duplicate company entries per resume.
"""
from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

import config

# ── helpers ─────────────────────────────────────────────────────────

def _conn():
    return psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.PG_DBNAME,
    )

# ── Schema DDL ──────────────────────────────────────────────────────

_DDL = """
DROP TABLE IF EXISTS experience     CASCADE;
DROP TABLE IF EXISTS resume_hobbies  CASCADE;
DROP TABLE IF EXISTS educations      CASCADE;
DROP TABLE IF EXISTS resumes         CASCADE;
DROP TABLE IF EXISTS hobbies         CASCADE;
DROP TABLE IF EXISTS companies       CASCADE;
DROP TABLE IF EXISTS universities    CASCADE;
DROP TABLE IF EXISTS cities          CASCADE;
DROP TABLE IF EXISTS users           CASCADE;

CREATE TABLE users (
    id            SERIAL       PRIMARY KEY,
    login         VARCHAR(50)  UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE cities (
    id   SERIAL       PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE hobbies (
    id   SERIAL       PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE companies (
    id   SERIAL       PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE universities (
    id   SERIAL       PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL
);

CREATE TABLE resumes (
    id         SERIAL       PRIMARY KEY,
    user_id    INT          UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    city_id    INT          NOT NULL        REFERENCES cities(id),
    full_name  VARCHAR(150) NOT NULL,
    birth_date DATE         NOT NULL,
    summary    TEXT
);

CREATE TABLE educations (
    id              SERIAL       PRIMARY KEY,
    resume_id       INT          NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    university_id   INT          NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
    degree          VARCHAR(150) NOT NULL,
    graduation_year INT          NOT NULL
);

CREATE TABLE resume_hobbies (
    resume_id INT NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    hobby_id  INT NOT NULL REFERENCES hobbies(id) ON DELETE CASCADE,
    PRIMARY KEY (resume_id, hobby_id)
);

CREATE TABLE experience (
    id         SERIAL       PRIMARY KEY,
    resume_id  INT          NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    company_id INT          NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    position   VARCHAR(100) NOT NULL,
    start_date DATE         NOT NULL,
    end_date   DATE,
    UNIQUE (resume_id, company_id)
);

-- Useful indexes for the 5 mandatory queries
CREATE INDEX idx_resumes_city          ON resumes(city_id);
CREATE INDEX idx_resumes_user          ON resumes(user_id);
CREATE INDEX idx_educations_resume     ON educations(resume_id);
CREATE INDEX idx_educations_university ON educations(university_id);
CREATE INDEX idx_experience_company    ON experience(company_id);
CREATE INDEX idx_experience_resume     ON experience(resume_id);
"""


# ── Seed ────────────────────────────────────────────────────────────

def seed(data: dict[str, Any]) -> None:
    """Drop-and-recreate schema, then bulk-insert all reference + candidate data."""
    conn = _conn()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(_DDL)

            # Reference tables ------------------------------------------------
            city_ids: dict[str, int] = {}
            for name in data["cities"]:
                cur.execute(
                    "INSERT INTO cities(name) VALUES (%s) RETURNING id", (name,)
                )
                city_ids[name] = cur.fetchone()[0]

            hobby_ids: dict[str, int] = {}
            for name in data["hobbies"]:
                cur.execute(
                    "INSERT INTO hobbies(name) VALUES (%s) RETURNING id", (name,)
                )
                hobby_ids[name] = cur.fetchone()[0]

            company_ids: dict[str, int] = {}
            for name in data["companies"]:
                cur.execute(
                    "INSERT INTO companies(name) VALUES (%s) RETURNING id", (name,)
                )
                company_ids[name] = cur.fetchone()[0]

            uni_ids: dict[str, int] = {}
            for name in data["universities"]:
                cur.execute(
                    "INSERT INTO universities(name) VALUES (%s) RETURNING id", (name,)
                )
                uni_ids[name] = cur.fetchone()[0]

            # Candidates -------------------------------------------------------
            for c in data["candidates"]:
                # user
                cur.execute(
                    "INSERT INTO users(login, password_hash) VALUES (%s, %s) RETURNING id",
                    (c["login"], c["password_hash"]),
                )
                user_id = cur.fetchone()[0]

                # resume
                cur.execute(
                    """INSERT INTO resumes
                       (user_id, city_id, full_name, birth_date, summary)
                       VALUES (%s, %s, %s, %s, %s)
                       RETURNING id""",
                    (user_id, city_ids[c["city"]],
                     c["full_name"], c["birth_date"], c["summary"]),
                )
                resume_id = cur.fetchone()[0]

                # educations (0, 1, or 2 degrees: Bachelor, Master)
                for edu in c["education"]:
                    cur.execute(
                        """INSERT INTO educations
                           (resume_id, university_id, degree, graduation_year)
                           VALUES (%s, %s, %s, %s)""",
                        (resume_id, uni_ids[edu["university"]],
                         edu["degree"], edu["graduation_year"]),
                    )

                # hobbies
                for h in c["hobbies"]:
                    cur.execute(
                        "INSERT INTO resume_hobbies(resume_id, hobby_id) VALUES (%s, %s)",
                        (resume_id, hobby_ids[h]),
                    )

                # experience
                for e in c["experience"]:
                    cur.execute(
                        """INSERT INTO experience
                           (resume_id, company_id, position, start_date, end_date)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (resume_id, company_ids[e["company"]],
                         e["position"], e["start_date"], e["end_date"]),
                    )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Queries ─────────────────────────────────────────────────────────

def q1_resume_by_login(login: str) -> dict | None:
    """Q1: Full resume for a specific user login."""
    sql = """
    SELECT u.login, r.full_name, r.birth_date, r.summary,
           c.name AS city
      FROM users u
      JOIN resumes r ON r.user_id = u.id
      JOIN cities  c ON c.id = r.city_id
     WHERE u.login = %s
    """
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (login,))
            row = cur.fetchone()
            if row is None:
                return None
            resume = dict(row)

            # education
            cur.execute("""
                SELECT un.name AS university, ed.degree, ed.graduation_year
                  FROM educations ed
                  JOIN universities un ON un.id = ed.university_id
                  JOIN resumes r       ON r.id = ed.resume_id
                  JOIN users u         ON u.id = r.user_id
                 WHERE u.login = %s
                 ORDER BY ed.graduation_year
            """, (login,))
            resume["education"] = [dict(r) for r in cur.fetchall()]

            # hobbies
            cur.execute("""
                SELECT h.name FROM hobbies h
                  JOIN resume_hobbies rh ON rh.hobby_id = h.id
                  JOIN resumes r         ON r.id = rh.resume_id
                  JOIN users u           ON u.id = r.user_id
                 WHERE u.login = %s
                 ORDER BY h.name
            """, (login,))
            resume["hobbies"] = [r["name"] for r in cur.fetchall()]

            # experience
            cur.execute("""
                SELECT co.name AS company, e.position, e.start_date, e.end_date
                  FROM experience e
                  JOIN companies co ON co.id = e.company_id
                  JOIN resumes r    ON r.id = e.resume_id
                  JOIN users u      ON u.id = r.user_id
                 WHERE u.login = %s
                 ORDER BY e.start_date
            """, (login,))
            resume["experience"] = [dict(r) for r in cur.fetchall()]

            return resume
    finally:
        conn.close()


def q2_all_hobbies() -> list[str]:
    """Q2: All unique hobbies across all resumes."""
    sql = """
    SELECT DISTINCT h.name
      FROM hobbies h
      JOIN resume_hobbies rh ON rh.hobby_id = h.id
     ORDER BY h.name
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def q3_all_cities() -> list[str]:
    """Q3: All unique cities across all resumes."""
    sql = """
    SELECT DISTINCT c.name
      FROM cities c
      JOIN resumes r ON r.city_id = c.id
     ORDER BY c.name
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def q4_hobbies_by_city(city: str) -> list[str]:
    """Q4: All hobbies of candidates living in a given city."""
    sql = """
    SELECT DISTINCT h.name
      FROM hobbies h
      JOIN resume_hobbies rh ON rh.hobby_id = h.id
      JOIN resumes r         ON r.id        = rh.resume_id
      JOIN cities  c         ON c.id        = r.city_id
     WHERE c.name = %s
     ORDER BY h.name
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (city,))
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def q5_shared_workplace() -> list[dict]:
    """
    Q5: Pairs of candidates who worked at the same company.
    Returns rows: (company, candidate_1, candidate_2).
    """
    sql = """
    SELECT co.name AS company,
           r1.full_name AS candidate_1,
           r2.full_name AS candidate_2
      FROM experience e1
      JOIN experience e2 ON e1.company_id = e2.company_id
                        AND e1.resume_id  < e2.resume_id
      JOIN companies co ON co.id = e1.company_id
      JOIN resumes r1   ON r1.id = e1.resume_id
      JOIN resumes r2   ON r2.id = e2.resume_id
     ORDER BY co.name, r1.full_name, r2.full_name
    """
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
