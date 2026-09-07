import math
import unittest

from preference import PreferenceService, SQLiteStorage


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.storage = SQLiteStorage(":memory:")
        self.addCleanup(self.storage.close)
        self.model = PreferenceService(self.storage)
        self.a = [0.7, 0.12, 0.04]
        self.b = [0.5, 0.25, 0.15]

    def test_near_liked_positive_near_disliked_negative(self):
        self.model.add_rating("u", "blush", self.a, 1)
        self.model.add_rating("u", "blush", self.b, -1)
        self.assertGreater(self.model.predict_preference("u", "blush", [0.71, 0.12, 0.05]), 0.8)
        self.assertLess(self.model.predict_preference("u", "blush", [0.51, 0.24, 0.15]), -0.8)

    def test_unknown_isolation_and_online_update(self):
        self.assertEqual(self.model.predict_preference("u", "lip", self.a), 0)
        self.model.add_rating("u", "lip", self.a, 1)
        self.assertEqual(self.model.predict_preference("u", "lip", self.a), 1)
        self.assertEqual(self.model.predict_preference("other", "lip", self.a), 0)
        self.assertEqual(self.model.predict_preference("u", "blush", self.a), 0)
        self.model.add_rating("u", "blush", self.a, -1)
        self.assertEqual(self.model.predict_preference("u", "blush", self.a), -1)
        self.assertEqual(self.model.predict_preference("u", "lip", self.a), 1)

    def test_conflict_differs_from_unknown_and_distant(self):
        unknown = self.model.explain_preference("u", "lip", self.a)
        self.assertIn("unknown", unknown["reason"][0])
        self.model.add_rating("u", "lip", self.a, 1)
        far = self.model.explain_preference("u", "lip", [0, 0, 0])
        self.assertLess(abs(far["score"]), 0.001)
        self.assertIn("Little nearby evidence", far["reason"][-1])
        self.model.add_rating("u", "lip", self.a, -1)
        conflict = self.model.explain_preference("u", "lip", self.a)
        self.assertEqual(conflict["score"], 0)
        self.assertIn("conflicts", conflict["reason"][-1])

    def test_three_nearest_and_exact_formula(self):
        for lightness in (0.7, 0.71, 0.72, 0.0):
            self.model.add_rating("u", "lip", [lightness, 0.12, 0.04], 1)
        result = self.model.explain_preference("u", "lip", self.a)
        expected = (1 + math.exp(-0.5 * 0.1 ** 2) + math.exp(-0.5 * 0.2 ** 2)) / 3
        self.assertAlmostEqual(result["score"], expected)
        self.assertEqual(result["evidence"]["liked"]["used_count"], 3)
        self.assertEqual(result["evidence"]["liked"]["total_count"], 4)

    def test_custom_distance_and_invalid_distance(self):
        self.model.add_rating("u", "lip", self.a, 1)
        custom = PreferenceService(self.storage, distance=lambda a, b: 0.1)
        self.assertAlmostEqual(custom.predict_preference("u", "lip", self.b), math.exp(-0.5))
        for value in (-1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PreferenceService(self.storage, distance=lambda a, b: value).predict_preference("u", "lip", self.a)

    def test_ranking_metadata_ties_no_mutation(self):
        self.model.add_rating("u", "lip", self.a, 1)
        candidates = [{"name": "far", "color": self.b},
                      {"name": "first", "color": self.a, "finish": "matte"},
                      {"name": "second", "color": self.a}]
        ranked = self.model.rank_colors("u", "lip", candidates)
        self.assertEqual([c["name"] for c in ranked], ["first", "second", "far"])
        self.assertEqual(ranked[0]["finish"], "matte")
        self.assertNotIn("score", candidates[1])
        self.assertTrue(ranked[0]["reason"])
        self.assertEqual(self.model.rank_colors("u", "lip", []), [])

    def test_comparisons_do_not_imply_likes(self):
        self.model.add_comparison("u", "lip", self.a, self.b, "b")
        self.assertEqual(self.model.predict_preference("u", "lip", self.b), 0)
        profile = self.model.get_profile("u")
        self.assertEqual(profile.categories["lip"].comparisons[0].preferred, "b")
        self.assertEqual(profile.categories["lip"].liked_colors, [])

    def test_invalid_inputs(self):
        for color in ([1, 2], [1, 2, 3, 4], [float("nan"), 0, 0], [0.5, float("inf"), 0],
                      [1.01, 0, 0], [True, 0, 0], "abc", None, ["0.5", 0, 0]):
            with self.subTest(color=color), self.assertRaises(ValueError):
                self.model.add_rating("u", "lip", color, 1)
        for rating in (0, 2, True, "1"):
            with self.subTest(rating=rating), self.assertRaises(ValueError):
                self.model.add_rating("u", "lip", self.a, rating)
        with self.assertRaises(ValueError):
            self.model.add_comparison("u", "lip", self.a, self.b, "tie")
        with self.assertRaises(ValueError):
            self.model.predict_preference("", "lip", self.a)
        with self.assertRaises(ValueError):
            self.model.add_rating("u", " ", self.a, 1)
        for bandwidth in (0, -1, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                PreferenceService(self.storage, bandwidth=bandwidth)
        for neighbors in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                PreferenceService(self.storage, neighbors=neighbors)
        self.assertEqual(self.model.get_profile("u").categories, {})

    def test_scores_bounded_on_synthetic_grid(self):
        for i in range(10):
            self.model.add_rating("u", "lip", [i / 10, 0.02 * i, -0.01 * i], 1 if i % 2 else -1)
        for i in range(21):
            score = self.model.predict_preference("u", "lip", [i / 20, 0.1, 0.05])
            self.assertTrue(-1 <= score <= 1)


if __name__ == "__main__":
    unittest.main()
