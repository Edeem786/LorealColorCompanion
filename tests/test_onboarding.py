import tempfile
import unittest
from pathlib import Path
from onboarding.server import create_app
from preference import SQLiteStorage


class RatingRequestTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)/"test.db"
        self.client = create_app(self.path).test_client()
        self.event = {"user_id":"u", "category":"lip", "event_id":"one", "color":[.7,.12,.04], "rating":1}

    def test_retries_and_conflicting_event_ids(self):
        for _ in range(2):
            response = self.client.post('/api/rating', json=self.event)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['rating_count'], 1)
        for change in ({'rating':-1}, {'preference_profile_id':'environment:Friends'}, {'user_id':'other'}):
            self.assertEqual(self.client.post('/api/rating',json={**self.event,**change}).status_code,400)
        with SQLiteStorage(self.path) as storage:
            self.assertEqual(len(storage.get_ratings('u','lip')),1)

    def test_invalid_feedback_writes_nothing(self):
        for change in ({'event_id':None},{'color':[1,2]},{'rating':0},{'user_id':''},{'category':''}):
            self.assertEqual(self.client.post('/api/rating',json={**self.event,**change}).status_code,400)
        with SQLiteStorage(self.path) as storage:
            self.assertEqual(storage.get_ratings('u','lip'),[])

    def test_aesthetic_save_retry(self):
        event = {**self.event, 'preference_profile_id':'environment:Friends'}
        for _ in range(2):
            self.assertEqual(self.client.post('/api/rating',json=event).json['rating_count'],1)
        with SQLiteStorage(self.path) as storage:
            self.assertEqual(storage.get_ratings('u','lip'),[])
            self.assertEqual(len(storage.get_ratings('u','lip','environment:Friends')),1)

    def test_removed_rank_endpoint(self):
        self.assertEqual(self.client.post('/api/rank',json={}).status_code,404)
