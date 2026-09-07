from pathlib import Path
import tempfile
import unittest

from preference import PreferenceService, SQLiteStorage


class StorageTests(unittest.TestCase):
    def test_file_roundtrip_and_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "preferences.db"
            with SQLiteStorage(path) as storage:
                model = PreferenceService(storage)
                event = model.add_rating("u", "lip", [0.7, 0.1, 0.04], 1)
                model.add_rating("u", "blush", [0.5, 0.2, 0.1], -1)
                comparison = model.add_comparison("u", "eyes", [0.5, 0, 0], [0.6, 0, 0], "a")
            with SQLiteStorage(path) as storage:
                profile = storage.get_profile("u")
                self.assertEqual(profile.categories["lip"].ratings, [event])
                self.assertEqual(profile.categories["eyes"].comparisons, [comparison])
                self.assertEqual(profile.categories["lip"].liked_colors, [(0.7, 0.1, 0.04)])
                self.assertEqual(profile.categories["blush"].disliked_colors, [(0.5, 0.2, 0.1)])
                self.assertIsNotNone(event.timestamp.tzinfo)
                self.assertEqual(PreferenceService(storage).predict_preference("u", "lip", [0.7, 0.1, 0.04]), 1)
                self.assertEqual(storage.get_profile("missing").categories, {})

    def test_sql_like_identifiers_are_literal_and_duplicates_retained(self):
        with SQLiteStorage(":memory:") as storage:
            user = "'; DROP TABLE ratings; --"
            for _ in range(2):
                storage.add_rating(user, "lip", [0.5, 0, 0], 1)
            self.assertEqual(len(storage.get_ratings(user, "lip")), 2)
            self.assertEqual(storage.get_ratings("other", "lip"), [])


if __name__ == "__main__":
    unittest.main()
