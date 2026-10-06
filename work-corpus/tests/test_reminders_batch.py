import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('bootstrap', Path(__file__).parents[1] / 'scripts/bootstrap_reminders.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def batch(tmp_path):
    path = tmp_path / 'source.json'
    path.write_text(json.dumps({'id': 'source-1', 'transcript': 'I will send the report.'}))
    return {'tasks': [{'source': {'source_path': str(path), 'source_id': 'source-1',
        'source_version_id': hashlib.sha256(path.read_bytes()).hexdigest(),
        'character_range': [0, len('I will send the report.')], 'excerpt': 'I will send the report.',
        'excerpt_sha256': hashlib.sha256(b'I will send the report.').hexdigest()}}]}


def test_exact_source_and_passage(tmp_path):
    bootstrap.validate(batch(tmp_path))


def test_changed_source_is_rejected(tmp_path):
    data = batch(tmp_path)
    Path(data['tasks'][0]['source']['source_path']).write_text('{}')
    with pytest.raises(ValueError, match='source_version_changed'):
        bootstrap.validate(data)


def test_wrong_passage_is_rejected(tmp_path):
    data = batch(tmp_path)
    data['tasks'][0]['source']['character_range'] = [1, len('I will send the report.')]
    with pytest.raises(ValueError, match='source_passage_mismatch'):
        bootstrap.validate(data)
