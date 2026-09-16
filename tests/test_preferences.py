import unittest
from preference import PreferenceService, SQLiteStorage


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.storage = SQLiteStorage(":memory:")
        self.addCleanup(self.storage.close)
        self.model = PreferenceService(self.storage)
        self.a = [.7, .12, .04]

    def result(self, color, user="u", category="lip"):
        return self.model.recommend(user, category, [{"name": "test", "color": color}])["results"][0]

    def test_likes_dislikes_and_unknown(self):
        self.assertIsNone(self.result(self.a)["score"])
        self.model.add_rating("u", "lip", self.a, 1)
        self.assertEqual(self.result(self.a)["score"], 1)
        self.assertIsNone(self.result(self.a, user="other")["score"])
        self.assertIsNone(self.result(self.a, category="blush")["score"])
        self.model.add_rating("u", "lip", self.a, -1)
        conflict = self.result(self.a)
        self.assertEqual(conflict["score"], 0)
        self.assertIn("conflicts", conflict["personal"]["reason"][-1])

    def test_black_white_do_not_support_gray(self):
        for color in ([0,0,0], [1,0,0]):
            self.model.add_rating("u", "lip", color, 1)
            self.assertEqual(self.result(color)["score"], 1)
        self.assertIsNone(self.result([.5,0,0])["score"])

    def test_unrelated_and_duplicate_likes_do_not_change_match(self):
        self.model.add_rating("u", "lip", self.a, 1)
        before = self.result([.71,.12,.04])["score"]
        for color in ([0,0,0], [1,0,0], self.a):
            self.model.add_rating("u", "lip", color, 1)
        result = self.result([.71,.12,.04])
        self.assertEqual(result["score"], before)
        self.assertEqual(len(result["personal"]["evidence"]["liked"]["nearest"]), 1)

    def test_cutoff_and_explicit_dislike(self):
        self.model.add_rating("u", "lip", [0,0,0], 1)
        self.assertGreater(self.result([.199,0,0])["score"], 0)
        self.assertIsNone(self.result([.2,0,0])["score"])
        self.model.add_rating("u", "lip", [.5,0,0], -1)
        self.assertEqual(self.result([.5,0,0])["score"], -1)

    def test_metadata_ties_and_no_mutation(self):
        self.model.add_rating("u", "lip", self.a, 1)
        products = [{"name":"first", "color":self.a, "finish":"matte"},
                    {"name":"second", "color":self.a}]
        result = self.model.recommend("u", "lip", products)["results"]
        self.assertEqual([r["name"] for r in result], ["first", "second"])
        self.assertEqual(result[0]["finish"], "matte")
        self.assertNotIn("score", products[0])
        self.assertEqual(self.model.recommend("u", "lip", [])["results"], [])

    def test_invalid_inputs(self):
        for color in ([1,2], [float("nan"),0,0], [1.1,0,0], [True,0,0], "bad"):
            with self.assertRaises(ValueError):
                self.result(color)
        for rating in (0, 2, True, "1"):
            with self.assertRaises(ValueError):
                self.model.add_rating("u", "lip", self.a, rating)
        for bandwidth in (0, -1, True, "bad", float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                PreferenceService(self.storage, bandwidth=bandwidth)
        for products in (None, [{}], [{"name":"missing"}], [{}]*1001):
            with self.assertRaises(ValueError):
                self.model.recommend("u", "lip", products)
        with self.assertRaises(ValueError):
            self.result(self.a, user="")

    def test_scores_bounded(self):
        for i in range(10):
            self.model.add_rating("u", "lip", [i/10,0,0], 1 if i%2 else -1)
        for i in range(21):
            score = self.result([i/20,0,0])["score"]
            self.assertTrue(score is None or -1 <= score <= 1)
