import sqlite3
import tempfile
from pathlib import Path
import unittest

from preference import PreferenceService, SQLiteStorage
from onboarding.server import dispatch


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.storage = SQLiteStorage(':memory:')
        self.addCleanup(self.storage.close)
        self.model = PreferenceService(self.storage)
        self.a = [0.7, 0.12, 0.04]
        self.b = [0.4, -0.1, -0.1]

    def test_isolation_and_comparison_roundtrip(self):
        self.model.add_rating('u', 'lip', self.a, 1)
        self.model.add_rating('u', 'lip', self.a, -1, 'environment:Friends')
        self.assertEqual(self.model.predict_preference('u', 'lip', self.a), 1)
        self.assertEqual(self.model.predict_preference('u', 'lip', self.a, 'environment:Friends'), -1)
        self.assertEqual(self.model.predict_preference('u', 'lip', self.a, 'environment:Work'), 0)
        self.assertEqual(self.model.predict_preference('other', 'lip', self.a, 'environment:Friends'), 0)
        self.model.add_comparison('u', 'lip', self.a, self.b, 'a', 'environment:Friends')
        profile = self.model.get_profile('u', 'environment:Friends')
        self.assertEqual(profile.preference_profile_id, 'environment:Friends')
        self.assertEqual(profile.categories['lip'].comparisons[0].preference_profile_id, 'environment:Friends')
        self.assertEqual(self.model.get_profile('u').categories['lip'].comparisons, [])

    def test_shared_disagreement_unknown_and_ties(self):
        self.model.add_rating('u', 'lip', self.a, 1)
        candidates = [{'name': 'A', 'color': self.a}, {'name': 'B', 'color': self.b}]
        results = self.model.rank_shared('u', 'lip', candidates, 'environment:Friends')
        self.assertTrue(all(r['overlap_score'] is None for r in results))
        self.model.add_rating('u', 'lip', self.a, -1, 'environment:Friends')
        results = self.model.rank_shared('u', 'lip', candidates, 'environment:Friends')
        self.assertEqual(results[0]['overlap_score'], -1)
        self.assertFalse(results[0]['shared_match'])
        self.assertEqual(results[1]['status'], 'insufficient_evidence')
        self.model.add_rating('u', 'lip', self.b, 1)
        self.model.add_rating('u', 'lip', self.b, 1, 'environment:Friends')
        results = self.model.rank_shared('u', 'lip', candidates + [{'name': 'B2', 'color': self.b}], 'environment:Friends')
        self.assertEqual([r['name'] for r in results], ['B', 'B2', 'A'])
        self.assertTrue(results[0]['shared_match'])
        self.assertEqual(results[0]['overlap_score'], min(results[0]['personal']['score'], results[0]['environment']['score']))
        with self.assertRaises(ValueError):
            self.model.rank_shared('u', 'lip', candidates, 'personal')

    def test_api_routes_environment_and_defaults_to_personal_ranking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.sqlite'
            event = {'user_id': 'u', 'event_id': 'a', 'color': self.a, 'rating': 1,
                     'preference_profile_id': 'environment:Friends'}
            dispatch('/api/rating', event, path)
            dispatch('/api/rating', event, path)
            candidates = [{'name': 'A', 'color': self.a}]
            self.assertEqual(dispatch('/api/rank', {'user_id': 'u', 'candidates': candidates}, path)['rating_count'], 0)
            result = dispatch('/api/rank', {'user_id': 'u', 'candidates': candidates, 'mode': 'shared',
                                           'environment_profile_id': 'environment:Friends'}, path)
            self.assertEqual(result['shared_match_count'], 0)
            self.assertEqual(result['results'][0]['status'], 'insufficient_evidence')
            with self.assertRaises(ValueError):
                dispatch('/api/rating', {**event, 'preference_profile_id': 'personal'}, path)

    def test_existing_database_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legacy.sqlite'
            with sqlite3.connect(path) as connection:
                connection.execute('''CREATE TABLE ratings (id INTEGER PRIMARY KEY, user_id TEXT,
                    category TEXT, l REAL, a REAL, b REAL, rating INTEGER, timestamp TEXT)''')
                connection.execute("INSERT INTO ratings VALUES (1, 'u', 'lip', .7, .12, .04, 1, '2026-09-07T00:00:00+00:00')")
            connection.close()
            for _ in range(2):
                with SQLiteStorage(path) as storage:
                    self.assertEqual(len(storage.get_ratings('u', 'lip')), 1)
                    self.assertEqual(storage.get_ratings('u', 'lip')[0].preference_profile_id, 'personal')
                    self.assertEqual(storage.get_ratings('u', 'lip', 'environment:Friends'), [])
