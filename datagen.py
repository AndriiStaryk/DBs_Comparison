# datagen.py
"""
Deterministic generator of exactly 750 realistic HR candidate profiles in English.
Produces a list[dict] consumed identically by PostgreSQL, MongoDB, and Neo4j seeders.

Key Rules & Predicates
----------------------
1. English reference pools: cities, hobbies, companies, universities, degrees,
   names, positions, summaries.
2. Education predicate:
   - A candidate CANNOT have a Master's degree without first having a Bachelor's degree.
   - Bachelor and Master can be from different universities and different specialties.
   - Master's graduation year is strictly after the Bachelor's graduation year (Bachelor + 2 years).
   - Distribution: ~20% no formal higher education, ~50% Bachelor's only, ~30% Bachelor + Master.
3. Experience & Hobbies:
   - Overlaps guaranteed across 15 cities, 20 hobbies, 20 companies, 10 universities.
   - 0-3 work experience stints per candidate (start/end dates consistent).
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import Any

from config import SEED, NUM_CANDIDATES

# ── Fixed reference pools (English) ─────────────────────────────────

CITIES: list[str] = [
    "Kyiv", "Lviv", "Odesa", "Kharkiv", "Dnipro",
    "Zaporizhzhia", "Vinnytsia", "Ivano-Frankivsk", "Ternopil", "Poltava",
    "Chernivtsi", "Rivne", "Uzhhorod", "Lutsk", "Kropyvnytskyi",
]

HOBBIES: list[str] = [
    "Chess", "Football", "Guitar", "Reading", "Travel",
    "Photography", "Cooking", "Running", "Swimming", "Cycling",
    "Yoga", "Programming", "Board Games", "Drawing", "Cinema",
    "Volunteering", "Dancing", "Gardening", "Fishing", "Rock Climbing",
]

COMPANIES: list[str] = [
    "Grammarly", "EPAM", "SoftServe", "GlobalLogic", "Luxoft",
    "DataArt", "Genesis", "Ajax Systems", "Intellias", "N-iX",
    "MacPaw", "Readdle", "Terrasoft", "Ciklum", "Sigma Software",
    "Infopulse", "Eleks", "Playrix", "Ring", "Uklon",
]

UNIVERSITIES: list[str] = [
    "Taras Shevchenko National University of Kyiv (CS)",
    "Taras Shevchenko National University of Kyiv (MechMat)",
    "Taras Shevchenko National University of Kyiv (Radiophysics)",
    "National University of Kyiv-Mohyla Academy",
    "Kyiv Polytechnic Institute (FICT)",
    "Kyiv Polytechnic Institute (IASA)",
    "Lviv Polytechnic National University",
    "Ivan Franko National University of Lviv",
    "Kharkiv National University of Radio Electronics",
    "Ukrainian Catholic University",
]

POSITIONS: list[str] = [
    "Junior Software Engineer", "Software Engineer", "Senior Software Engineer",
    "DevOps Engineer", "QA Engineer", "Data Analyst", "Project Manager",
    "Product Manager", "UI/UX Designer", "Machine Learning Engineer",
    "Frontend Developer", "Backend Developer", "Full-Stack Developer",
    "System Administrator", "Business Analyst", "Technical Writer",
    "Scrum Master", "CTO", "Team Lead", "Intern",
]

BACHELOR_DEGREES: list[str] = [
    "Bachelor of Computer Science",
    "Bachelor of Applied Mathematics",
    "Bachelor of Software Engineering",
    "Bachelor of Cybersecurity",
    "Bachelor of Information Systems",
]

MASTER_DEGREES: list[str] = [
    "Master of Computer Science",
    "Master of Applied Mathematics",
    "Master of Software Engineering",
    "Master of Cybersecurity",
    "Master of Information Systems",
]

# ── First / Last names (Latin transliteration) ──────────────────────

_FIRST_NAMES: list[str] = [
    "Oleksandr", "Andrii", "Dmytro", "Maksym", "Artem",
    "Ivan", "Mykhailo", "Serhii", "Oleh", "Viktor",
    "Taras", "Bohdan", "Roman", "Yurii", "Pavlo",
    "Mariia", "Anna", "Olena", "Kateryna", "Nataliia",
    "Sofiia", "Viktoriia", "Yuliia", "Iryna", "Daryna",
    "Tetiana", "Oksana", "Liudmyla", "Halyna", "Valentyna",
    "Yaroslav", "Vladyslav", "Nazar", "Denys", "Yevhen",
    "Alina", "Diana", "Maryna", "Liliia", "Khrystyna",
]

_LAST_NAMES: list[str] = [
    "Shevchenko", "Kovalenko", "Bondarenko", "Tkachenko", "Kravchenko",
    "Melnyk", "Oliinyk", "Lysenko", "Moroz", "Savchenko",
    "Petrenko", "Klymenko", "Pavlenko", "Rudenko", "Honcharenko",
    "Kuzmenko", "Polishchuk", "Stepanenko", "Marchenko", "Romanenko",
    "Kovalchuk", "Levchenko", "Sydorenko", "Vasylenko", "Tymchenko",
    "Yakovenko", "Fedorenko", "Kostenko", "Hryshchenko", "Danylenko",
]


def _hash_password(plain: str) -> str:
    """SHA-256 hex digest for passwords."""
    return hashlib.sha256(plain.encode()).hexdigest()


def _random_date(start_year: int, end_year: int, rng: random.Random) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def generate_candidates(n: int = NUM_CANDIDATES, seed: int = SEED) -> dict[str, Any]:
    """
    Generate exactly `n` candidate records adhering to all constraints.
    Returns:
      - ``cities``, ``hobbies``, ``companies``, ``universities``
      - ``candidates``: list[dict] with user, resume, education, hobbies, experience
    """
    rng = random.Random(seed)
    candidates: list[dict[str, Any]] = []

    for i in range(1, n + 1):
        first = rng.choice(_FIRST_NAMES)
        last = rng.choice(_LAST_NAMES)
        full_name = f"{first} {last}"

        login = f"user_{i:04d}"
        password_hash = _hash_password(f"pass_{i:04d}")

        birth_date = _random_date(1980, 2003, rng)
        city = rng.choice(CITIES)

        # Hobbies: 1 to 4 unique hobbies
        hobby_count = rng.randint(1, 4)
        hobbies = rng.sample(HOBBIES, k=min(hobby_count, len(HOBBIES)))

        # ── Education Logic with Predicate ───────────────────────────
        # Rule: A person CANNOT have a Master's without a Bachelor's.
        # Distribution:
        # - 20%: No higher education (self-taught / career changer)
        # - 50%: Bachelor's degree only
        # - 30%: Bachelor's degree + Master's degree (can be different uni / specialty)
        edu_choice = rng.random()
        education: list[dict[str, Any]] = []

        if edu_choice >= 0.20:
            # 1. Bachelor's is mandatory for anyone with higher education
            bachelor_grad_year = min(birth_date.year + rng.randint(21, 23), 2023)
            bachelor_uni = rng.choice(UNIVERSITIES)
            bachelor_deg = rng.choice(BACHELOR_DEGREES)

            education.append({
                "university": bachelor_uni,
                "degree": bachelor_deg,
                "graduation_year": bachelor_grad_year,
            })

            # 2. Master's degree (only if candidate has Bachelor's)
            if edu_choice >= 0.70:
                master_grad_year = min(bachelor_grad_year + 2, 2025)
                # Master's can be at a different university and different specialty
                master_uni = rng.choice(UNIVERSITIES)
                master_deg = rng.choice(MASTER_DEGREES)

                education.append({
                    "university": master_uni,
                    "degree": master_deg,
                    "graduation_year": master_grad_year,
                })

        # Experience: 0 to 3 stints
        exp_count = rng.randint(0, 3)
        experience: list[dict[str, Any]] = []
        used_companies: set[str] = set()
        for _ in range(exp_count):
            company = rng.choice(COMPANIES)
            if company in used_companies:
                continue
            used_companies.add(company)

            start = _random_date(2016, 2024, rng)
            # 30% currently employed (end_date = None)
            end = None if rng.random() < 0.30 else _random_date(
                start.year, min(start.year + 3, 2025), rng
            )
            if end is not None and end < start:
                start, end = end, start

            experience.append({
                "company": company,
                "position": rng.choice(POSITIONS),
                "start_date": start,
                "end_date": end,
            })

        summary_snippets = [
            f"Software Engineer with expertise in modern technologies, based in {city}.",
            f"Results-driven IT specialist with strong focus on performance and reliability.",
            f"Passionate developer with background in distributed systems and algorithms.",
            f"Dedicated professional with experience in software engineering and cloud infrastructure.",
            f"Motivated engineer focused on building robust and scalable applications.",
        ]

        candidates.append({
            "login": login,
            "password_hash": password_hash,
            "full_name": full_name,
            "birth_date": birth_date,
            "city": city,
            "summary": rng.choice(summary_snippets),
            "hobbies": hobbies,
            "education": education,  # list of 0, 1, or 2 degrees (Bachelor, or Bachelor+Master)
            "experience": experience,
        })

    return {
        "cities": CITIES,
        "hobbies": HOBBIES,
        "companies": COMPANIES,
        "universities": UNIVERSITIES,
        "candidates": candidates,
    }
