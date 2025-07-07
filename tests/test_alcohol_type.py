import os
import sys
import json
import pytest

# Ensure SScraper.py is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from SScraper import get_alcohol_type, load_alcohol_types

# Load test data from alcohol_types.json
TYPES = load_alcohol_types()

def test_json_file_loads():
    assert isinstance(TYPES, list)
    assert any('type' in t and 'keywords' in t for t in TYPES)

def test_bourbon_detection():
    product = {'title': 'Rare Bourbon Whiskey', 'product_type': '', 'body_html': '', 'tags': []}
    assert get_alcohol_type(product) == 'Bourbon'

def test_beer_detection():
    product = {'title': 'Craft IPA', 'product_type': 'Beer', 'body_html': '', 'tags': []}
    assert get_alcohol_type(product) == 'Beer'

def test_non_alcoholic_detection():
    product = {'title': 'Heineken 0.0', 'product_type': 'Beer', 'body_html': '', 'tags': []}
    assert get_alcohol_type(product) == 'Non-Alcoholic Beer'

def test_soda_detection():
    product = {'title': 'Dr. Pepper Can', 'product_type': '', 'body_html': '', 'tags': []}
    assert get_alcohol_type(product) == 'Soda/Non-Alcoholic'

def test_other_detection():
    product = {'title': 'Mystery Drink', 'product_type': '', 'body_html': '', 'tags': []}
    assert get_alcohol_type(product) == 'Other'
