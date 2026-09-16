from pathlib import Path
import tempfile
import unittest
from onboarding.server import create_app


class CvdProfileTests(unittest.TestCase):
    def test_save_load_update_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'db.sqlite'
            client=create_app(database).test_client()
            self.assertIsNone(client.get('/api/cvd-profile?user_id=a').json['profile'])
            payload={'user_id':'a','type':'deutan','severity':'moderate'}
            response=client.post('/api/cvd-profile',json=payload)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['profile']['source'],'user_entered_diagnosis')
            self.assertEqual(response.json['profile']['severity_level'],2)
            fresh=create_app(database).test_client()
            self.assertEqual(fresh.get('/api/cvd-profile?user_id=a').json['profile']['severity'],'moderate')
            self.assertIsNone(fresh.get('/api/cvd-profile?user_id=b').json['profile'])
            self.assertEqual(fresh.post('/api/cvd-profile',json={**payload,'severity':'mild'}).json['profile']['severity'],'mild')
            for invalid in ({'severity':'unsure'},{'type':'unsure'},{'severity':.5},{'user_id':''}):
                self.assertEqual(fresh.post('/api/cvd-profile',json={**payload,**invalid}).status_code,400)
            self.assertEqual(fresh.get('/api/cvd-profile?user_id=a').json['profile']['severity'],'mild')
            self.assertEqual(fresh.get('/api/cvd-profile?user_id=a').json['profile']['severity_level'],1)
            result=fresh.post('/api/cvd-profile',json={**payload,'severity':'severe'})
            self.assertEqual(result.json['profile']['severity_level'],3)
            rank=fresh.post('/api/recommend',json={'user_id':'a','candidates':[]}).json
            self.assertEqual(rank['personal_rating_count'],0)
            with fresh.get('/cvd-form.js') as response:
                self.assertEqual(response.status_code,200)
