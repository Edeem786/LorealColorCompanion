import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from preference import SQLiteStorage


class StorageTests(unittest.TestCase):
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"test.db"
            with SQLiteStorage(path) as storage:
                event = storage.add_rating("u", "lip", [.7,.1,.04], 1)
                self.assertIsNotNone(event.timestamp.tzinfo)
            with SQLiteStorage(path) as storage:
                self.assertEqual(storage.get_ratings("u", "lip")[0].color_vector, (.7,.1,.04))
                self.assertEqual(storage.get_ratings("missing", "lip"), [])

    def test_old_database_and_retry_records_survive(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"old.db"
            with sqlite3.connect(path) as connection:
                connection.executescript("""
                    CREATE TABLE ratings(id INTEGER PRIMARY KEY, user_id TEXT, category TEXT,
                        l REAL, a REAL, b REAL, rating INTEGER, timestamp TEXT);
                    INSERT INTO ratings VALUES(1,'u','lip',.7,.1,.04,1,'2026-09-01T00:00:00+00:00');
                    CREATE TABLE comparisons(note TEXT);
                    INSERT INTO comparisons VALUES('preserve me');
                    CREATE TABLE onboarding_events(event_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                """)
                connection.execute("INSERT INTO onboarding_events VALUES (?,?)",
                    ("old-event", json.dumps(["u","lip",[.7,.1,.04],1])))
            connection.close()
            with SQLiteStorage(path) as storage:
                storage.add_rating("u", "lip", [.7,.1,.04], 1, event_id="old-event")
                self.assertEqual(len(storage.get_ratings("u", "lip")), 1)
                self.assertEqual(storage.connection.execute("SELECT note FROM comparisons").fetchone()[0], "preserve me")
                self.assertEqual(storage.get_ratings("u", "lip")[0].preference_profile_id, "personal")
