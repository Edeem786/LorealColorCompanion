import io
import json
from pathlib import Path
import tempfile
import unittest

from onboarding.server import create_app


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
        for endpoint in ('/api/detect-region', '/api/detect-lip-shades', '/api/detect-skin-shades'):
            self.assertEqual(client.post(endpoint, json={}).status_code, 404)
