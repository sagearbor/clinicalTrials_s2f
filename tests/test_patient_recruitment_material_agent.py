import os
import sys
import json
import yaml
from pathlib import Path
from docx import Document
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import patient_recruitment_material_agent as agent

class MockLLMMessage:
    def __init__(self, content):
        self.content = content

class MockLLMChoice:
    def __init__(self, content):
        self.message = MockLLMMessage(content)

class MockLLMResponse:
    def __init__(self, content=""):
        self.choices = [MockLLMChoice(content)]


def create_docx(path: Path, text: str) -> None:
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)


def test_generate_materials_creates_files(tmp_path, mocker):
    protocol = tmp_path / "protocol.docx"
    insights = tmp_path / "insights.json"
    create_docx(protocol, "Protocol text")
    insights.write_text(json.dumps({"demo": "adult"}))

    mocker.patch('scripts.patient_recruitment_material_agent.completion', return_value=MockLLMResponse("Ad copy\nFlyer"))
    mocker.patch('scripts.patient_recruitment_material_agent.get_llm_model_name', return_value='test-model')

    out_dir = tmp_path / "out"
    paths = agent.generate_materials(str(protocol), str(insights), str(out_dir))

    assert Path(paths["docx"]).exists()
    assert Path(paths["html"]).exists()
    assert Path(paths["png"]).exists()

    doc = Document(paths["docx"])
    assert "Ad copy" in doc.paragraphs[1].text


def test_update_checklist(tmp_path):
    checklist_data = [
        {'agentId': '2.200', 'name': 'Patient Recruitment Material Generator', 'status': 0}
    ]
    file_path = tmp_path / 'checklist.yml'
    file_path.write_text(yaml.safe_dump(checklist_data))

    agent.update_checklist(str(file_path), 90)
    updated = yaml.safe_load(file_path.read_text())
    assert updated[0]['status'] == 90


def test_write_progress_log_creates_valid_json(tmp_path):
    log_dir = tmp_path / 'logs'
    status = 50
    summary = 'Created materials'

    path_str = agent.write_progress_log(str(log_dir), status, summary)
    path = Path(path_str)
    assert path.exists()
    assert path.name.startswith(f"2.200-{status}-")

    content = json.loads(path.read_text())
    assert content['agentId'] == '2.200'
    assert content['status'] == status
    assert content['summary'] == summary
    assert 'timestamp' in content
