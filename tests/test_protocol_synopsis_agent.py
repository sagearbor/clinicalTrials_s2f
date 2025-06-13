import json
from pathlib import Path
import os
import sys

import pytest
import yaml

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import protocol_synopsis_agent as agent

class DummyChoice:
    def __init__(self, content):
        self.message = type('msg', (), {'content': content})

class DummyResponse:
    def __init__(self, content):
        self.choices = [DummyChoice(content)]

def test_generate_synopsis_creates_docx(tmp_path, mocker):
    input_data = {
        'therapeuticArea': 'Oncology',
        'productName': 'ABC123',
        'studyPhase': 'Phase 2',
        'primaryObjective': 'Evaluate safety'
    }
    mock_resp = DummyResponse('Rationale\nStudy Design')
    mocker.patch('litellm.completion', return_value=mock_resp)

    out_dir = tmp_path / 'output'
    path = agent.generate_synopsis(input_data, str(out_dir))
    assert Path(path).exists()


def test_update_checklist(tmp_path):
    checklist = [
        {'agentId': '1.100', 'name': 'Protocol Synopsis Generation Agent', 'status': 0, 'dependencies': []}
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

