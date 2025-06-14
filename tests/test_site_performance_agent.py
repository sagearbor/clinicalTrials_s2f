import os
import sys
import json
import yaml
from pathlib import Path
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import site_performance_agent as agent

class DummyMessage:
    def __init__(self, content):
        self.content = content

class DummyChoice:
    def __init__(self, content):
        self.message = DummyMessage(content)

class DummyResponse:
    def __init__(self, content=""):
        self.choices = [DummyChoice(content)]

def create_csv(path: Path, header: str, rows: list[str]):
    lines = [header] + rows
    path.write_text("\n".join(lines))

def test_generate_report_creates_json(tmp_path, mocker):
    internal_csv = tmp_path / "internal.csv"
    public_csv = tmp_path / "public.csv"
    population_json = tmp_path / "population.json"
    out_dir = tmp_path / "out"

    create_csv(internal_csv, "site_id,enrollment_rate,data_quality", [
        "site1,0.8,0.9",
        "site2,0.6,0.95"
    ])
    create_csv(public_csv, "site_id,geography", [
        "site1,US",
        "site2,EU"
    ])
    population_json.write_text(json.dumps({"counts": {"US": 100, "EU": 50}}))

    mocker.patch('scripts.site_performance_agent.completion', return_value=DummyResponse("summary"))
    mocker.patch('scripts.site_performance_agent.get_llm_model_name', return_value='model')

    path = agent.generate_report(str(internal_csv), str(public_csv), str(population_json), str(out_dir))

    data = json.loads(Path(path).read_text())
    ranked_ids = [r['site_id'] for r in data['ranked_sites']]
    assert ranked_ids == ['site1', 'site2']
    assert data['summary'] == 'summary'

def test_update_checklist(tmp_path):
    checklist_data = [
        {'agentId': '1.300', 'name': 'Site Performance Evaluation Agent', 'status': 0, 'dependencies': []}
    ]
    file_path = tmp_path / 'checklist.yml'
    file_path.write_text(yaml.safe_dump(checklist_data))

    agent.update_checklist(str(file_path), 75)

    updated = yaml.safe_load(file_path.read_text())
    assert updated[0]['status'] == 75

def test_write_progress_log(tmp_path):
    log_dir = tmp_path / 'logs'
    path = agent.write_progress_log(str(log_dir), 50, 'done')

    log_path = Path(path)
    assert log_path.exists()
    assert log_path.name.startswith('1.300-50-')
    data = json.loads(log_path.read_text())
    assert data['agentId'] == '1.300'
    assert data['status'] == 50
    assert data['summary'] == 'done'
    assert 'timestamp' in data
