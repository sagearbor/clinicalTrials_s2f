import json
from pathlib import Path
import os
import sys

import pytest
import yaml

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import patient_population_agent as agent

class DummyChoice:
    def __init__(self, content):
        self.message = type('msg', (), {'content': content})

class DummyResponse:
    def __init__(self, content):
        self.choices = [DummyChoice(content)]

def test_generate_report_creates_json(tmp_path, mocker):
    input_data = {
        'inclusionCriteria': ['age > 50'],
        'exclusionCriteria': ['diabetes'],
        'geographies': ['US']
    }
    mock_counts = {'US': 100}
    mocker.patch('requests.post', return_value=mocker.Mock(json=lambda: mock_counts, raise_for_status=lambda: None))
    mock_resp = DummyResponse('Summary')
    mocker.patch('litellm.completion', return_value=mock_resp)

    out_dir = tmp_path / 'output'
    path = agent.generate_report(input_data, str(out_dir), 'http://example.com')
    assert Path(path).exists()
    data = json.loads(Path(path).read_text())
    assert data['counts'] == mock_counts


def test_update_checklist(tmp_path):
    checklist = [
        {'agentId': '1.200', 'name': 'Patient Population Analysis Agent', 'status': 0, 'dependencies': []}
    ]
    file_path = tmp_path / 'checklist.yml'
    file_path.write_text(yaml.safe_dump(checklist))

    agent.update_checklist(str(file_path), 80)

    updated = yaml.safe_load(file_path.read_text())
    assert updated[0]['status'] == 80


def test_write_progress_log(tmp_path):
    log_dir = tmp_path / 'logs'
    path = agent.write_progress_log(str(log_dir), 50, 'done')
    assert Path(path).exists()
    assert path.startswith(str(log_dir))

