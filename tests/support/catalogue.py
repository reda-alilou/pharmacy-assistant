"""Reviewed import profile, independent of retired parser/raw-snapshot layout."""
import json
from pathlib import Path


def profile():
    return json.loads(Path(__file__).with_name('catalogue_profile.json').read_text(encoding='utf-8'))
