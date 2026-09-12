import io
from pathlib import Path
import unittest

from onboarding.server import create_app


class ShadeDetectionTests(unittest.TestCase):
    def upload(self, detector, category='lip', image=None):
        client = create_app(detect_shades=detector).test_client()
        return client.post('/api/detect-shades', data={
            'category': category,
            'image': (io.BytesIO(image if image is not None else
                      Path('tests/palette-fixture.png').read_bytes()), 'reference.png'),
        })

    def test_category_dispatch_and_rgb(self):
        calls = []
        def detector(image, category):
            calls.append(category)
            return [[180, 80, 100]]
        for category in ('lip', 'blush'):
            result = self.upload(detector, category)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['shades'], [[180, 80, 100]])
        self.assertEqual(calls, ['lip', 'blush'])

    def test_empty_and_invalid_requests(self):
        self.assertEqual(self.upload(lambda *_: []).json, {'shades': []})
        def never_called(*_):
            self.fail('Invalid uploads must not reach the detector')
        self.assertEqual(self.upload(never_called, 'eye').status_code, 400)
        self.assertEqual(self.upload(never_called, image=b'bad').status_code, 400)

    def test_bad_output_and_missing_model(self):
        def missing(*_):
            raise FileNotFoundError('model')
        for detector in (missing, lambda *_: [[256, 0, 0]], lambda *_: [[True, 0, 0]]):
            with self.assertLogs('onboarding.server', level='ERROR'):
                result = self.upload(detector)
            self.assertEqual(result.status_code, 503)
            self.assertIn('error', result.json)
