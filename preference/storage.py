"""SQLite ratings and safe request retries. Existing comparison tables are untouched."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import PreferenceEvent, validate_color, validate_key

DATABASE = Path(__file__).resolve().parent.parent / "data" / "preferences.db"


class SQLiteStorage:
    def __init__(self, path=DATABASE):
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
                timestamp TEXT NOT NULL,
                preference_profile_id TEXT NOT NULL DEFAULT 'personal'
            );
            CREATE TABLE IF NOT EXISTS onboarding_events (
                event_id TEXT PRIMARY KEY, payload TEXT NOT NULL
            );
        """)
        # Upgrade older databases without deleting their ratings or other tables.
        with self.connection:
            columns = {row[1] for row in self.connection.execute("PRAGMA table_info(ratings)")}
            if "preference_profile_id" not in columns:
                self.connection.execute("ALTER TABLE ratings ADD COLUMN preference_profile_id TEXT NOT NULL DEFAULT 'personal'")
            self.connection.execute("CREATE INDEX IF NOT EXISTS ratings_profile ON ratings(user_id, preference_profile_id, category)")

    def add_rating(self, user_id, category, color, rating, preference_profile_id="personal", *, event_id=None):
        validate_key(user_id, "user_id")
        validate_key(category, "category")
        validate_key(preference_profile_id, "preference_profile_id")
        vector = validate_color(color)
        if isinstance(rating, bool) or rating not in (-1, 1):
            raise ValueError("rating must be -1 or 1.")
        if event_id is not None and (not isinstance(event_id, str) or not 1 <= len(event_id) <= 100):
            raise ValueError("A valid event_id is required.")
        event = PreferenceEvent(user_id, category, vector, int(rating), datetime.now(timezone.utc), preference_profile_id)
        # Preserve the signature format used by previous versions of the website.
        signature_parts = [user_id, category, vector, rating]
        if preference_profile_id != "personal":
            signature_parts.append(preference_profile_id)
        signature = json.dumps(signature_parts)
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            if event_id is not None:
                previous = self.connection.execute("SELECT payload FROM onboarding_events WHERE event_id=?", (event_id,)).fetchone()
                if previous:
                    if previous[0] != signature:
                        raise ValueError("Event ID already belongs to different feedback.")
                    return event
                self.connection.execute("INSERT INTO onboarding_events VALUES (?, ?)", (event_id, signature))
            self.connection.execute(
                "INSERT INTO ratings(user_id, category, l, a, b, rating, timestamp, preference_profile_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, category, *vector, event.rating, event.timestamp.isoformat(), preference_profile_id),
            )
        return event

    def save_skin_tones(self, user_id, colors):
        """Replace measured samples in their own category; [] clears them."""
        validate_key(user_id, "user_id")
        if not isinstance(colors, list) or len(colors) > 12:
            raise ValueError("Provide up to 12 skin-tone samples.")
        vectors = list(dict.fromkeys(validate_color(color) for color in colors))
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection:
            self.connection.execute("DELETE FROM ratings WHERE user_id=? AND category='skin_tone' AND preference_profile_id='personal'", (user_id,))
            self.connection.executemany(
                "INSERT INTO ratings(user_id,category,l,a,b,rating,timestamp,preference_profile_id) VALUES (?, 'skin_tone', ?, ?, ?, 1, ?, 'personal')",
                [(user_id, *color, timestamp) for color in vectors])
        return vectors

    def get_ratings(self, user_id, category, preference_profile_id="personal"):
        validate_key(user_id, "user_id")
        validate_key(category, "category")
        validate_key(preference_profile_id, "preference_profile_id")
        rows = self.connection.execute(
            "SELECT * FROM ratings WHERE user_id=? AND category=? AND preference_profile_id=? ORDER BY id",
            (user_id, category, preference_profile_id),
        )
        return [PreferenceEvent(row["user_id"], row["category"], (row["l"], row["a"], row["b"]),
                row["rating"], datetime.fromisoformat(row["timestamp"]), row["preference_profile_id"]) for row in rows]

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
