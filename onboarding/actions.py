"""Preference request handling, independent of Flask."""
import json
from pathlib import Path
from preference import PreferenceService, SQLiteStorage

DATABASE = Path(__file__).resolve().parent.parent / "data" / "preferences.db"

def dispatch(path, payload, database=DATABASE):
    if not isinstance(payload, dict):
        raise ValueError("Expected an object.")
    user = payload.get("user_id")
    from preference.models import validate_key
    profile_id = payload.get("preference_profile_id", "personal")
    validate_key(profile_id, "preference_profile_id")
    with SQLiteStorage(database) as storage:
        model = PreferenceService(storage)
        if path == "/api/rating":
            # A browser-generated event ID makes retries safe without changing core event semantics.
            event_id = payload.get("event_id")
            if not isinstance(event_id, str) or not 1 <= len(event_id) <= 100:
                raise ValueError("A valid event_id is required.")
            color = payload.get("color")
            rating = payload.get("rating")
            from preference.models import validate_color, validate_key
            validate_key(user, "user_id")
            color = validate_color(color)
            if isinstance(rating, bool) or rating not in (-1, 1):
                raise ValueError("rating must be -1 or 1.")
            storage.connection.execute("""CREATE TABLE IF NOT EXISTS onboarding_events (
                event_id TEXT PRIMARY KEY, payload TEXT NOT NULL)""")
            signature = json.dumps([user, "lip", color, rating])
            if profile_id != "personal":
                signature = json.dumps([user, "lip", color, rating, profile_id])
            # Single transaction covers deduplication and the underlying preference event.
            from datetime import datetime, timezone
            with storage.connection:
                storage.connection.execute("BEGIN IMMEDIATE")
                old = storage.connection.execute("SELECT payload FROM onboarding_events WHERE event_id=?", (event_id,)).fetchone()
                if old:
                    if old[0] != signature:
                        raise ValueError("Event ID already belongs to different feedback.")
                else:
                    storage.connection.execute("INSERT INTO onboarding_events VALUES (?, ?)", (event_id, signature))
                    storage.connection.execute(
                        "INSERT INTO ratings(user_id, category, l, a, b, rating, timestamp, preference_profile_id) VALUES (?, 'lip', ?, ?, ?, ?, ?, ?)",
                        (user, *color, rating, datetime.now(timezone.utc).isoformat(), profile_id),
                    )
            return {"saved": True, "rating_count": len(storage.get_ratings(user, "lip", profile_id))}
        if path == "/api/rank":
            candidates = payload.get("candidates")
            if not isinstance(candidates, list) or len(candidates) > 50:
                raise ValueError("Provide up to 50 candidates.")
            mode = payload.get("mode", "personal")
            if mode not in ("personal", "shared", "weighted"):
                raise ValueError("Unknown ranking mode.")
            if mode == "weighted":
                return model.rank_weighted(user, "lip", candidates,
                    personal_weight=payload.get("personal_weight", 1.0),
                    environment_profile_id=payload.get("environment_profile_id"))
            if mode == "shared":
                results = model.rank_shared(user, "lip", candidates, payload.get("environment_profile_id"))
                return {"results": results, "mode": "shared", "shared_match_count": sum(r["shared_match"] for r in results)}
            return {"results": model.rank_colors(user, "lip", candidates),
                    "rating_count": len(storage.get_ratings(user, "lip"))}
        raise ValueError("Unknown endpoint.")

