import io
import json
from pathlib import Path
import tempfile
import unittest

from onboarding.server import create_app
from onboarding.integrations import MakeupRegion, AccessibilityAssessment


class FlaskTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database=Path(directory.name)/'test.db'
        self.catalog_directory=Path(directory.name)/'catalogs'
        self.catalog_directory.mkdir()
        (self.catalog_directory/'lip.json').write_text(json.dumps([{'id':'a','product_name':'Test','shade_name':'A','category':'lip','color':{'L':.7,'a':.12,'b':.04}}]))
        self.image=Path('tests/palette-fixture.png').read_bytes()

    def client(self, **adapters):
        app=create_app(self.database, catalog_directory=self.catalog_directory, **adapters)
        app.config['TESTING']=True
        return app.test_client()

    def upload(self, client):
        return client.post('/api/detect-region',data={'image':(io.BytesIO(self.image),'reference.png')})

    def test_routes_and_request_errors(self):
        client=self.client()
        for path in ('/','/app.js','/colors.js','/style.css'):
            with client.get(path) as response:
                self.assertEqual(response.status_code,200)
        self.assertEqual(client.get('/server.py').status_code,404)
        self.assertEqual(client.post('/api/rating',data='{',content_type='application/json').status_code,400)
        self.assertEqual(client.post('/api/rating',data='text').status_code,415)
        self.assertEqual(client.post('/api/rating',json={},headers={'Origin':'https://example.com'}).status_code,403)
        self.assertEqual(client.post('/api/rating',data='x'*100001,content_type='application/json').status_code,413)
        self.assertFalse(client.get('/api/capabilities').json['region_detection'])
        self.assertIsNone(self.upload(client).json['region'])

    def test_vision_contract_and_no_implicit_rating(self):
        calls=[]
        def detector(image_bytes, category):
            calls.append((image_bytes,category))
            return MakeupRegion(.2,.5,.4,.1)
        client=self.client(detect_region=detector)
        self.assertEqual(self.upload(client).json['region']['x'],.2)
        self.assertEqual(calls,[(self.image,'lip')])
        self.assertTrue(client.get('/api/capabilities').json['region_detection'])
        result=client.post('/api/recommend',json={'user_id':'u','category':'lip'}).json
        self.assertEqual(result['personal_rating_count'],0)
        self.assertEqual(client.post('/api/detect-region').status_code,400)

    def test_invalid_detector_falls_back(self):
        result=self.upload(self.client(detect_region=lambda *_:None))
        self.assertIsNone(result.json['region'])
        with self.assertLogs('onboarding.server',level='ERROR'):
            result=self.upload(self.client(detect_region=lambda *_:MakeupRegion(.9,0,.2,.1)))
        self.assertEqual(result.status_code,503)
        self.assertIsNone(result.json['region'])
        self.assertIn('manually',result.json['message'])

    def test_cvd_attached_without_changing_preferences(self):
        calls=[]
        def assessor(user,category,color):
            calls.append((user,category,color))
            return AccessibilityAssessment(.2,'Example test assessment')
        client=self.client(assess_accessibility=assessor)
        event={'user_id':'u','event_id':'one','color':[.7,.12,.04],'rating':1}
        for _ in range(2):
            self.assertEqual(client.post('/api/rating',json=event).json['rating_count'],1)
        request={'user_id':'u','category':'lip'}
        rated=client.post('/api/recommend',json=request).json['results'][0]
        plain=self.client().post('/api/recommend',json=request).json['results'][0]
        self.assertEqual(rated['score'],plain['score'])
        self.assertEqual(rated['accessibility']['score'],.2)
        self.assertIsNone(plain['accessibility'])
        self.assertEqual(calls,[('u','lip',(.7,.12,.04))])
        invalid=self.client(assess_accessibility=lambda *_:AccessibilityAssessment(2,'invalid'))
        with self.assertLogs('onboarding.server',level='ERROR'):
            fallback=invalid.post('/api/recommend',json=request).json['results'][0]
        self.assertIsNone(fallback['accessibility'])
        self.assertEqual(fallback['score'],1)
