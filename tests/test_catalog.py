import json
from pathlib import Path
import tempfile
import unittest
from onboarding.catalog import load_catalog
from onboarding.server import create_app


class CatalogTests(unittest.TestCase):
    def test_supplied_catalog(self):
        products=load_catalog('blush')
        self.assertEqual(len(products),26)
        self.assertEqual(products[0]['color'],[.68,.32,.28])
        lip=load_catalog('lip')
        self.assertEqual(len(lip),52)
        self.assertEqual(lip[0]['color'],[.65,.22,.14])
        self.assertEqual(lip[0]['source_category'],'lipstick')
        with self.assertRaises(ValueError):
            load_catalog('../blush')

    def test_recommendation_uses_catalog_and_category(self):
        with tempfile.TemporaryDirectory() as folder:
            client=create_app(Path(folder)/'test.db').test_client()
            color=load_catalog('blush')[0]['color']
            rating={'user_id':'u','event_id':'lip-rating','color':color,'rating':1,'category':'lip'}
            self.assertEqual(client.post('/api/rating',json=rating).status_code,200)
            request={'user_id':'u','category':'blush','mode':'weighted','candidates':[{'name':'Fake','color':color}]}
            response=client.post('/api/recommend',json=request)
            self.assertEqual(response.status_code,200)
            self.assertTrue(all(p['score'] is None for p in response.json['results']))
            self.assertEqual(len(response.json['results']),26)
            rating.update(category='blush',event_id='blush-rating')
            self.assertEqual(client.post('/api/rating',json=rating).status_code,200)
            top=client.post('/api/recommend',json=request).json['results'][0]
            self.assertEqual(top['id'],'loreal_lumi_liquid_dewy_peach')
            self.assertEqual(top['score'],1)
            self.assertEqual(top['color_source'],'estimated')
            self.assertEqual(client.post('/api/recommend',json={**request,'category':'missing'}).status_code,400)
            catalogs=client.get('/api/catalogs').json['catalogs']
            self.assertIn({'category':'blush','count':26},catalogs)

    def test_new_catalog_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'eyeshadow.json'
            product={'id':'a','product_name':'Example','shade_name':'01','category':'eyeshadow','color':{'L':.5,'a':.1,'b':0}}
            path.write_text(json.dumps([product]))
            self.assertEqual(load_catalog('eyeshadow',folder)[0]['id'],'a')
            path.write_text(json.dumps([product,product]))
            with self.assertRaises(ValueError):load_catalog('eyeshadow',folder)
            path.write_text(json.dumps([{**product,'category':'lip'}]))
            with self.assertRaises(ValueError):load_catalog('eyeshadow',folder)

    def test_lip_catalog_recommendations(self):
        with tempfile.TemporaryDirectory() as folder:
            client=create_app(Path(folder)/'test.db').test_client()
            product=load_catalog('lip')[0]
            response=client.post('/api/rating',json={'user_id':'lip-user','event_id':'lip-one',
                'category':'lip','color':product['color'],'rating':1})
            self.assertEqual(response.status_code,200)
            response=client.post('/api/recommend',json={'user_id':'lip-user','category':'lip','mode':'weighted'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(response.json['results']),52)
            top=response.json['results'][0]
            self.assertEqual(top['id'],product['id'])
            self.assertEqual(top['score'],1)
            self.assertTrue(all(p['category']=='lip' for p in response.json['results']))
            self.assertIn({'category':'lip','count':52},client.get('/api/catalogs').json['catalogs'])
