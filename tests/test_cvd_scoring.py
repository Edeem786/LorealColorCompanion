import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from preference import PreferenceService, SQLiteStorage
from onboarding.server import create_app
from colormatcher.cvdsimulator import make_cvd_transform, SEVERITY_MAP


class CvdScoringTests(unittest.TestCase):
    def test_transform_personal_only_once_and_keep_originals(self):
        with SQLiteStorage(":memory:") as storage:
            service = PreferenceService(storage)
            reference = [.6, .2, 0]
            candidate = [.6, -.2, 0]
            service.add_rating('u', 'lip', reference, 1)
            service.add_rating('u', 'lip', candidate, 1, 'environment:Friends')
            products = [{'name':'candidate','color':candidate}]
            original_products = copy.deepcopy(products)
            calls = []
            def transform(color):
                calls.append(tuple(color))
                return [color[0], 0, color[2]]
            plain = service.recommend('u','lip',products, personal_weight=.6,
                                      environment_profile_id='environment:Friends')['results'][0]
            result = service.recommend('u','lip',products, personal_weight=.6,
                                       environment_profile_id='environment:Friends',
                                       personal_transform=transform)['results'][0]
            self.assertIsNone(plain['score'])
            self.assertEqual(result['score'],1)
            self.assertEqual(result['environment'],plain['environment'])
            self.assertEqual(calls,[tuple(reference),tuple(candidate)])
            self.assertEqual(products,original_products)
            self.assertEqual(storage.get_ratings('u','lip')[0].color_vector,tuple(reference))
            self.assertEqual(result['color'],candidate)
            self.assertEqual(result['personal']['evidence']['liked']['nearest'][0]['color'],[.6,0,0])

    def test_dislikes_transformed_and_zero_personal_weight_skips_transform(self):
        with SQLiteStorage(":memory:") as storage:
            service = PreferenceService(storage)
            service.add_rating('u','lip',[.6,.2,0],-1)
            products=[{'name':'test','color':[.6,-.2,0]}]
            transform=lambda color: [.6,0,0]
            self.assertEqual(service.recommend('u','lip',products,personal_transform=transform)['results'][0]['score'],-1)
            service.add_rating('u','lip',products[0]['color'],1,'environment:Friends')
            def unused(_):
                self.fail('Aesthetic-only scoring must not simulate colors')
            result=service.recommend('u','lip',products,personal_weight=0,
                    environment_profile_id='environment:Friends',personal_transform=unused)
            self.assertEqual(result['results'][0]['score'],1)

    def test_presets_and_invalid_settings(self):
        self.assertEqual(SEVERITY_MAP,{1:.33,2:.66,3:1.0})
        for cvd_type, severity in [('other',1),('deutan',True),('protan',0),('tritan',.66)]:
            with self.assertRaises(ValueError):
                make_cvd_transform(cvd_type,severity)


class CvdRequestTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database=Path(folder.name)/'test.db'
        self.client=create_app(self.database).test_client()
        self.client.post('/api/rating',json={'user_id':'u','category':'lip',
            'event_id':'like','color':[.6,.1,0],'rating':1})

    def save_profile(self, cvd_type='deutan'):
        self.client.post('/api/cvd-profile',json={'user_id':'u','type':cvd_type,'severity':'moderate'})

    def recommend(self):
        response=self.client.post('/api/recommend',json={'user_id':'u','category':'lip'})
        self.assertEqual(response.status_code,200)
        return response.json

    def test_saved_profile_reaches_transform(self):
        self.save_profile()
        with patch('onboarding.server.make_cvd_transform',return_value=lambda color:[.6,0,0]) as factory:
            result=self.recommend()
        factory.assert_called_once_with('deutan',2)
        self.assertTrue(result['cvd']['applied'])
        self.assertEqual(result['cvd']['severity'],.66)
        self.assertEqual(result['results'][0]['score'],1)
        self.assertNotIn('accessibility',result['results'][0])

    def test_missing_unsupported_and_dependency_failure_are_labelled(self):
        self.assertFalse(self.recommend()['cvd']['applied'])
        self.save_profile('other')
        with patch('onboarding.server.make_cvd_transform') as factory:
            self.assertIn('not supported',self.recommend()['cvd']['message'])
            factory.assert_not_called()
        self.save_profile()
        with patch('onboarding.server.make_cvd_transform',side_effect=ImportError):
            result=self.recommend()
            self.assertFalse(result['cvd']['applied'])
            self.assertIn('requirements-cvd.txt',result['cvd']['message'])
        with patch('onboarding.server.make_cvd_transform',return_value=lambda color: [float('nan'),0,0]):
            with self.assertLogs('onboarding.server',level='ERROR'):
                self.assertFalse(self.recommend()['cvd']['applied'])


@unittest.skipUnless(importlib.util.find_spec('colour') and importlib.util.find_spec('numpy'),
                     'Install requirements-cvd.txt for real Machado checks')
class RealMachadoTests(unittest.TestCase):
    def test_known_deutan_matrix_output_and_finite_presets(self):
        import numpy as np
        import colour
        # Published full-severity deutan matrix applied to linear sRGB red.
        red = colour.XYZ_to_Oklab(colour.RGB_to_XYZ([1,0,0], 'sRGB'))
        expected_rgb=[.367322,.280085,0]  # Negative blue channel clipped.
        expected=colour.XYZ_to_Oklab(colour.RGB_to_XYZ(expected_rgb,'sRGB'))
        actual=make_cvd_transform('deutan',3)(red)
        np.testing.assert_allclose(actual,expected,atol=2e-4)
        for kind in ('protan','deutan','tritan'):
            for level in (1,2,3):
                transform=make_cvd_transform(kind,level)
                self.assertTrue(np.isfinite(transform(red)).all())
                np.testing.assert_allclose(transform([0,0,0]),[0,0,0],atol=1e-8)
                np.testing.assert_allclose(transform([1,0,0]),[1,0,0],atol=2e-4)

    def test_actual_simulator_through_flask(self):
        with tempfile.TemporaryDirectory() as folder:
            client=create_app(Path(folder)/'test.db').test_client()
            client.post('/api/cvd-profile',json={'user_id':'real','type':'deutan','severity':'mild'})
            client.post('/api/rating',json={'user_id':'real','category':'lip','event_id':'one',
                        'color':[.65,.22,.14],'rating':1})
            result=client.post('/api/recommend',json={'user_id':'real','category':'lip'}).json
            self.assertTrue(result['cvd']['applied'])
            self.assertEqual(result['results'][0]['score'],1)
