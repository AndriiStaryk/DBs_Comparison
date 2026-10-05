# config.py
"""
Centralised connection parameters for all three databases.
Override via environment variables when running outside Docker's default network.
"""
import os

# ── PostgreSQL ──────────────────────────────────────────────────────
PG_HOST     = os.getenv("PG_HOST", "localhost")
PG_PORT     = int(os.getenv("PG_PORT", 5432))
PG_USER     = os.getenv("PG_USER", "hr_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "hr_pass")
PG_DBNAME   = os.getenv("PG_DBNAME", "hr_resumes")

# ── MongoDB ─────────────────────────────────────────────────────────
MONGO_HOST     = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT     = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER     = os.getenv("MONGO_USER", "hr_user")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "hr_pass")
MONGO_DBNAME   = os.getenv("MONGO_DBNAME", "hr_resumes")

# ── Neo4j ───────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "hr_pass_neo4j")

# ── Seed control ────────────────────────────────────────────────────
SEED = 42          # reproducible random state
NUM_CANDIDATES = 750  # exact candidate count (per user requirement)

