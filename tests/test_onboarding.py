from pathlib import Path
import tempfile
import unittest
from onboarding.server import dispatch
from preference import SQLiteStorage


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "test.db"
        self.event = {"user_id": "test", "event_id": "one", "color": [0.7, 0.12, 0.04], "rating": 1}

    def test_confirmed_rating_retry_and_ranking(self):
        for _ in range(2):
            self.assertEqual(dispatch('/api/rating', self.event, self.path)['rating_count'], 1)
        result = dispatch('/api/rank', {"user_id": "test", "candidates": [
            {"name": "near", "color": self.event['color']}, {"name": "far", "color": [0.1, 0, 0]}]}, self.path)
        self.assertEqual(result['results'][0]['name'], 'near')
        self.assertEqual(result['results'][0]['score'], 1)
        with SQLiteStorage(self.path) as storage:
            self.assertEqual(storage.get_ratings('test', 'blush'), [])

    def test_conflicting_retry_rejected(self):
        dispatch('/api/rating', self.event, self.path)
        with self.assertRaises(ValueError):
            dispatch('/api/rating', {**self.event, 'rating': -1}, self.path)

    def test_invalid_and_skip_do_not_save(self):
        for override in ({'rating': None}, {'rating': True}, {'color': [2, 0, 0]}, {'user_id': ''}):
            with self.assertRaises(ValueError):
                dispatch('/api/rating', {**self.event, **override}, self.path)
        result = dispatch('/api/rank', {'user_id': 'test', 'candidates': []}, self.path)
        self.assertEqual(result['rating_count'], 0)
