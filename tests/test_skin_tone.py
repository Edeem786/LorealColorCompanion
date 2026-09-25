import tempfile
import unittest
from pathlib import Path
from preference import PreferenceService, SQLiteStorage
from onboarding.server import create_app


class SkinToneTests(unittest.TestCase):
    def test_storage_replaces_isolates_and_preserves_preferences(self):
        with SQLiteStorage(':memory:') as storage:
            storage.add_rating('u','blush',[.6,.1,0],1)
            storage.save_skin_tones('u',[[.6,.1,0],[.6,.1,0]])
            self.assertEqual(len(storage.get_ratings('u','skin_tone')),1)
            storage.save_skin_tones('u',[[.7,.05,.02]])
            self.assertEqual(storage.get_ratings('u','skin_tone')[0].color_vector,(.7,.05,.02))
            for invalid in ([[float('nan'),0,0]], [[.5,0,0]]*13, None):
                with self.assertRaises(ValueError):
                    storage.save_skin_tones('u',invalid)
            self.assertEqual(len(storage.get_ratings('u','skin_tone')),1)
            self.assertEqual(storage.get_ratings('other','skin_tone'),[])
            storage.save_skin_tones('u',[])
            self.assertEqual(storage.get_ratings('u','skin_tone'),[])
            self.assertEqual(len(storage.get_ratings('u','blush')),1)

    def test_blush_factor_ranking_skip_and_lip_unchanged(self):
        with SQLiteStorage(':memory:') as storage:
            service=PreferenceService(storage)
            a,b=[.6,.1,0],[.6,-.1,0]
            products=[{'name':'opposite','color':b},{'name':'same','color':a}]
            for category in ('lip','blush'):
                for color in (a,b):
                    service.add_rating('u',category,color,1)
            before=service.recommend('u','lip',products)
            storage.save_skin_tones('u',[a])
            ranked=service.recommend('u','blush',products)
            self.assertEqual(ranked['results'][0]['name'],'same')
            self.assertAlmostEqual(ranked['results'][0]['score'],1)
            self.assertAlmostEqual(ranked['results'][1]['score'],0)
            self.assertEqual(ranked['personal_rating_count'],2)
            self.assertEqual(service.recommend('u','lip',products),before)
            skipped=service.recommend('u','blush',products,use_skin_tone=False)
            self.assertEqual(skipped['results'][0]['name'],'opposite')
            self.assertIsNone(skipped['results'][0]['skin_factor'])
            with self.assertRaises(ValueError):
                service.recommend('u','blush',products,use_skin_tone='false')

    def test_skin_samples_do_not_create_preference_support(self):
        with SQLiteStorage(':memory:') as storage:
            service=PreferenceService(storage)
            storage.save_skin_tones('u',[[.6,.1,0]])
            products=[{'name':'test','color':[.6,-.1,0]}]
            self.assertIsNone(service.recommend('u','blush',products)['results'][0]['score'])
            service.add_rating('u','blush',products[0]['color'],-1)
            self.assertEqual(service.recommend('u','blush',products)['results'][0]['score'],-1)

    def test_api_persistence_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'test.db'
            client=create_app(database).test_client()
            self.assertEqual(client.get('/api/skin-tone?user_id=u').json,{'colors':[]})
            samples={'user_id':'u','colors':[[.65,.07,.04]]}
            self.assertEqual(client.post('/api/skin-tone',json=samples).status_code,200)
            fresh=create_app(database).test_client()
            self.assertEqual(fresh.get('/api/skin-tone?user_id=u').json['colors'],samples['colors'])
            self.assertEqual(fresh.get('/api/skin-tone?user_id=other').json['colors'],[])
            self.assertEqual(fresh.post('/api/skin-tone',json={'user_id':'u','colors':[[2,0,0]]}).status_code,400)
            self.assertEqual(fresh.post('/api/skin-tone',json={'user_id':'u','colors':[]}).json['colors'],[])
            with fresh.get('/skin-form.js') as response:
                self.assertEqual(response.status_code,200)
