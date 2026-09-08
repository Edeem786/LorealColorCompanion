"""Load one JSON product list per makeup category."""
import json
from pathlib import Path
import re
from preference.models import validate_color, validate_key

CATALOG_DIR = Path(__file__).resolve().parent.parent / 'catalogs'


def load_catalog(category, directory=CATALOG_DIR):
    if not isinstance(category, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', category):
        raise ValueError('Invalid catalog category.')
    path = Path(directory) / f'{category}.json'
    if not path.is_file():
        raise ValueError(f'No catalog for {category}. Add catalogs/{category}.json.')
    products = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(products, list):
        raise ValueError('Catalog must be a JSON list.')
    result, ids = [], set()
    for product in products:
        if not isinstance(product, dict):
            raise ValueError('Each product must be an object.')
        for key in ('id', 'product_name', 'shade_name'):
            validate_key(product.get(key), key)
        if product['id'] in ids:
            raise ValueError('Duplicate product ID: ' + product['id'])
        ids.add(product['id'])
        if product.get('category') != category:
            raise ValueError('Product category must match its catalog filename.')
        color = product.get('color')
        if not isinstance(color, dict) or not all(key in color for key in ('L','a','b')):
            raise ValueError('Catalog color must contain normalized OKLab L, a, b.')
        vector = validate_color([color['L'], color['a'], color['b']])
        result.append({**product, 'name': product['product_name'] + ' — ' + product['shade_name'],
                       'color': list(vector)})
    return result


def list_catalogs(directory=CATALOG_DIR):
    return [{'category': path.stem, 'count': len(load_catalog(path.stem, directory))}
            for path in sorted(Path(directory).glob('*.json'))]
