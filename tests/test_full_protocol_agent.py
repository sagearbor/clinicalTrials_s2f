import os
from pathlib import Path
import yaml
from docx import Document

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import full_protocol_agent as agent

class DummyChoice:
    def __init__(self, content):
        self.message = type('msg', (), {'content': content})

class DummyResponse:
    def __init__(self, content):
        self.choices = [DummyChoice(content)]


def create_docx(path: Path, text: str) -> None:
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)


def test_generate_full_protocol_creates_docx(tmp_path, mocker):
    synopsis = tmp_path / 'synopsis.docx'
    template = tmp_path / 'template.docx'
    create_docx(synopsis, 'Synopsis content')
    create_docx(template, 'Template section')

    mock_resp = DummyResponse('Section A\nSection B')
    mocker.patch('litellm.completion', return_value=mock_resp)

    out_dir = tmp_path / 'out'
    path = agent.generate_full_protocol(str(synopsis), str(template), str(out_dir))
    assert Path(path).exists()


def test_update_checklist(tmp_path):
    checklist = [
        {'agentId': '1.400', 'name': 'Full Protocol Generation Agent', 'status': 0, 'dependencies': []}
    ]
    file_path = tmp_path / 'checklist.yml'
    file_path.write_text(yaml.safe_dump(checklist))

    agent.update_checklist(str(file_path), 90)

    updated = yaml.safe_load(file_path.read_text())
    assert updated[0]['status'] == 90


def test_write_progress_log(tmp_path):
    log_dir = tmp_path / 'logs'
    path = agent.write_progress_log(str(log_dir), 50, 'done')
    assert Path(path).exists()
    assert path.startswith(str(log_dir))
