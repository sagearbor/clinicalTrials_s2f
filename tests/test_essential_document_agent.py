import os
import sys
import json
import yaml
from pathlib import Path
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import essential_document_agent as agent


class DummyMessage:
    def __init__(self, content):
        self.content = content

class DummyChoice:
    def __init__(self, content):
        self.message = DummyMessage(content)

class DummyResponse:
    def __init__(self, content=""):
        self.choices = [DummyChoice(content)]


def test_generate_dashboard_creates_json(tmp_path, mocker):
    site_file = tmp_path / "sites.yml"
    checklist_file = tmp_path / "checklist.yml"
    submissions = tmp_path / "submissions"
    submissions.mkdir()

    yaml.safe_dump(["site1", "site2"], site_file.open("w"))
    yaml.safe_dump(["1572", "cv"], checklist_file.open("w"))

    # Create documents for site1 only
    site1_dir = submissions / "site1"
    site1_dir.mkdir()
    (site1_dir / "1572.pdf").write_text("signed by PI on 2024-01-01")
    (site1_dir / "cv.docx").write_text("curriculum vitae signed")

    mocker.patch('scripts.essential_document_agent.completion', return_value=DummyResponse('PASS'))
    mocker.patch('scripts.essential_document_agent.get_llm_model_name', return_value='model')

    out_dir = tmp_path / "out"
    path = agent.generate_dashboard(str(site_file), str(checklist_file), str(submissions), str(out_dir))

    data = json.loads(Path(path).read_text())
    assert data['site1']['1572']['received'] is True
    assert data['site2']['1572']['received'] is False


def test_update_checklist(tmp_path):
    checklist_data = [
        {'agentId': '2.100', 'name': 'Essential Document Collection Agent', 'status': 0}
    ]
    file_path = tmp_path / 'checklist.yml'
    file_path.write_text(yaml.safe_dump(checklist_data))

    agent.update_checklist(str(file_path), 80)

    updated = yaml.safe_load(file_path.read_text())
    assert updated[0]['status'] == 80


def test_write_progress_log(tmp_path):
    log_dir = tmp_path / 'logs'
    path = agent.write_progress_log(str(log_dir), 50, 'done')

    log_path = Path(path)
    assert log_path.exists()
    assert log_path.name.startswith('2.100-50-')
    data = json.loads(log_path.read_text())
    assert data['agentId'] == '2.100'
    assert data['status'] == 50
    assert data['summary'] == 'done'
    assert 'timestamp' in data
