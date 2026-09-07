"""Small SQLite event store; writes are committed before returning."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    CategoryPreference, ComparisonEvent, PreferenceEvent, UserPreferenceProfile,
    validate_color, validate_key,
)


class SQLiteStorage:
    def __init__(self, path: str | Path = "data/preferences.db"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL, category TEXT NOT NULL,
                l REAL NOT NULL, a REAL NOT NULL, b REAL NOT NULL,
                rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ratings_user_category ON ratings(user_id, category);
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL, category TEXT NOT NULL,
                a_l REAL NOT NULL, a_a REAL NOT NULL, a_b REAL NOT NULL,
                b_l REAL NOT NULL, b_a REAL NOT NULL, b_b REAL NOT NULL,
                preferred TEXT NOT NULL CHECK (preferred IN ('a', 'b')),
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS comparisons_user_category
                ON comparisons(user_id, category);
        """)

        # Additive migration preserves existing feedback as personal preferences.
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            for table in ("ratings", "comparisons"):
                columns = {row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")}
                if "preference_profile_id" not in columns:
                    self.connection.execute(f"ALTER TABLE {table} ADD COLUMN preference_profile_id TEXT NOT NULL DEFAULT 'personal'")
                self.connection.execute(f"CREATE INDEX IF NOT EXISTS {table}_profile ON {table}(user_id, preference_profile_id, category)")

    def add_rating(self, user_id, category, color, rating, preference_profile_id="personal") -> PreferenceEvent:
        validate_key(user_id, "user_id")
        validate_key(preference_profile_id, "preference_profile_id")
        validate_key(category, "category")
        vector = validate_color(color)
        if isinstance(rating, bool) or rating not in (-1, 1):
            raise ValueError("rating must be -1 or 1.")
        event = PreferenceEvent(user_id, category, vector, int(rating), datetime.now(timezone.utc), preference_profile_id)
        with self.connection:
            self.connection.execute(
                "INSERT INTO ratings(user_id, category, l, a, b, rating, timestamp, preference_profile_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, category, *vector, event.rating, event.timestamp.isoformat(), preference_profile_id),
            )
        return event

    def add_comparison(self, user_id, category, color_a, color_b, preferred, preference_profile_id="personal") -> ComparisonEvent:
        validate_key(user_id, "user_id")
        validate_key(preference_profile_id, "preference_profile_id")
        validate_key(category, "category")
        a, b = validate_color(color_a), validate_color(color_b)
        if preferred not in ("a", "b"):
            raise ValueError("preferred must be 'a' or 'b'.")
        event = ComparisonEvent(user_id, category, a, b, preferred, datetime.now(timezone.utc), preference_profile_id)
        with self.connection:
            self.connection.execute(
                """INSERT INTO comparisons(user_id, category, a_l, a_a, a_b, b_l, b_a, b_b, preferred, timestamp, preference_profile_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, category, *a, *b, preferred, event.timestamp.isoformat(), preference_profile_id),
            )
        return event

    def get_ratings(self, user_id, category, preference_profile_id="personal") -> list[PreferenceEvent]:
        validate_key(user_id, "user_id")
        validate_key(preference_profile_id, "preference_profile_id")
        validate_key(category, "category")
        rows = self.connection.execute(
            "SELECT * FROM ratings WHERE user_id = ? AND category = ? AND preference_profile_id = ? ORDER BY id", (user_id, category, preference_profile_id)
        )
        return [self._rating(row) for row in rows]

    @staticmethod
    def _rating(row):
        return PreferenceEvent(row["user_id"], row["category"], (row["l"], row["a"], row["b"]),
                               row["rating"], datetime.fromisoformat(row["timestamp"]), row["preference_profile_id"])

    def get_profile(self, user_id, preference_profile_id="personal") -> UserPreferenceProfile:
        validate_key(user_id, "user_id")
        validate_key(preference_profile_id, "preference_profile_id")
        profile = UserPreferenceProfile(user_id, preference_profile_id=preference_profile_id)
        for row in self.connection.execute("SELECT * FROM ratings WHERE user_id = ? AND preference_profile_id = ? ORDER BY id", (user_id, preference_profile_id)):
            profile.categories.setdefault(row["category"], CategoryPreference()).ratings.append(self._rating(row))
        for row in self.connection.execute("SELECT * FROM comparisons WHERE user_id = ? AND preference_profile_id = ? ORDER BY id", (user_id, preference_profile_id)):
            event = ComparisonEvent(user_id, row["category"], (row["a_l"], row["a_a"], row["a_b"]),
                                    (row["b_l"], row["b_a"], row["b_b"]), row["preferred"],
                                    datetime.fromisoformat(row["timestamp"]), row["preference_profile_id"])
            profile.categories.setdefault(row["category"], CategoryPreference()).comparisons.append(event)
        return profile

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
