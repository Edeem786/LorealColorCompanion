"""Run with python -m onboarding.server; local prototype, not a public service."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3

from preference import PreferenceService, SQLiteStorage

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT.parent / "data" / "preferences.db"


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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                 "/colors.js": ("colors.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if self.path not in files:
            self.send_error(404)
            return
        name, kind = files[self.path]
        self.reply(200, (ROOT / name).read_bytes(), kind + "; charset=utf-8")

    def reply(self, status, body, kind="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            if self.headers.get("Origin") not in (None, f"http://{self.headers.get('Host')}"):
                raise ValueError("Cross-origin requests are not supported.")
            if self.headers.get("Content-Type") != "application/json":
                raise ValueError("Expected application/json.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 100_000:
                raise ValueError("Invalid request size.")
            result = dispatch(self.path, json.loads(self.rfile.read(length)))
            self.reply(200, json.dumps(result).encode())
        except (ValueError, TypeError, KeyError) as exc:
            self.reply(400, json.dumps({"error": str(exc)}).encode())
        except sqlite3.Error:
            self.reply(500, json.dumps({"error": "Could not save or read feedback. Please retry."}).encode())


if __name__ == "__main__":
    print("Open http://127.0.0.1:8000 — press Ctrl+C to stop.", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
