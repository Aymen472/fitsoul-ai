"""Idempotent script to seed Pakistani foods from CSV into the configured database."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.nutrition import get_food_db
from app.db import ProfileRepository, get_engine, get_session_factory, init_db


def main() -> int:
    """Load foods from CSV and upsert them into the foods table."""
    init_db(get_engine())
    food_db = get_food_db()
    session_factory = get_session_factory()
    with session_factory() as session:
        count = ProfileRepository.seed_foods(session, food_db.all_foods())
    print(f"Seeded {count} foods into the database.")
    return count


if __name__ == "__main__":
    main()
