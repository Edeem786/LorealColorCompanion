import unittest
from preference import PreferenceService, SQLiteStorage
from pathlib import Path
import tempfile


class WeightedTests(unittest.TestCase):
    def setUp(self):
        self.storage=SQLiteStorage(':memory:')
        self.addCleanup(self.storage.close)
        self.model=PreferenceService(self.storage)
        self.a=[0.6,0.1,0.04]
        self.b=[0.65,0.15,0.04]
        self.candidates=[{'name':'A','color':self.a},{'name':'B','color':self.b}]
        self.model.add_rating('u','lip',self.a,1)
        self.model.add_rating('u','lip',self.b,1,'environment:Friends')

    def test_weight_changes_order_and_exact_score(self):
        for weight, first in ((0.6,'A'),(0.4,'B'),(1,'A'),(0,'B')):
            result=self.model.recommend('u','lip',self.candidates,personal_weight=weight,environment_profile_id='environment:Friends')
            self.assertEqual(result['results'][0]['name'],first)
            for item in result['results']:
                self.assertAlmostEqual(item['score'],weight*item['personal']['score']+(1-weight)*item['environment']['score'])
                self.assertTrue(-1<=item['score']<=1)

    def test_missing_optional_set_forces_personal(self):
        for environment in (None,'environment:Missing'):
            result=self.model.recommend('u','lip',self.candidates,personal_weight=0,environment_profile_id=environment)
            self.assertEqual(result['personal_weight'],1)
            self.assertEqual(result['results'][0]['score'],1)

    def test_unknown_active_side_and_zero_weight_side(self):
        self.model.add_rating('u','lip',[0,0,0],1,'environment:Distant')
        result=self.model.recommend('u','lip',self.candidates,personal_weight=.6,environment_profile_id='environment:Distant')
        self.assertIsNone(result['results'][0]['score'])
        result=self.model.recommend('u','lip',self.candidates,personal_weight=1,environment_profile_id='environment:Distant')
        self.assertEqual(result['results'][0]['score'],1)

    def test_invalid_weights(self):
        for weight in (-.1,1.1,True,'60',None,float('nan'),float('inf')):
            with self.subTest(weight=weight),self.assertRaises(ValueError):
                self.model.recommend('u','lip',self.candidates,personal_weight=weight)
