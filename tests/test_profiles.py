import unittest
from preference import PreferenceService, SQLiteStorage


class ProfileTests(unittest.TestCase):
    def test_profiles_remain_separate(self):
        with SQLiteStorage(":memory:") as storage:
            service = PreferenceService(storage)
            color = [.7,.12,.04]
            products = [{"name":"A", "color":color}]
            service.add_rating("u", "lip", color, 1)
            service.add_rating("u", "lip", color, -1, "environment:Friends")
            result = service.recommend("u", "lip", products, personal_weight=.6,
                                       environment_profile_id="environment:Friends")["results"][0]
            self.assertEqual(result["personal"]["score"], 1)
            self.assertEqual(result["environment"]["score"], -1)
            self.assertAlmostEqual(result["score"], .2)
            self.assertEqual(storage.get_ratings("u", "lip", "environment:Work"), [])
            self.assertEqual(storage.get_ratings("other", "lip"), [])
            with self.assertRaises(ValueError):
                service.recommend("u", "lip", products, environment_profile_id="personal")
