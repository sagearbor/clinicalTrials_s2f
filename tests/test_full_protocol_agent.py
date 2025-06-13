import os
import sys
import json
import yaml
from pathlib import Path
from docx import Document

# Add project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import full_protocol_agent as agent

# Helper classes to mock the litellm response object
class DummyMessage:
    def __init__(self, content):
        self.content = content

class DummyChoice:
    def __init__(self, content):
        self.message = DummyMessage(content)

class DummyResponse:
    def __init__(self, content):
        self.choices = [DummyChoice(content)]

# Helper function to create a dummy docx file for testing
def create_docx(path: Path, text: str) -> None:
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)

# Test for the main agent logic
def test_generate_full_protocol_creates_docx(tmp_path, mocker):
    # 1. Setup: Create mock input files
    synopsis = tmp_path / 'synopsis.docx'
    template = tmp_path / 'template.docx'
    create_docx(synopsis, 'Synopsis content')
    create_docx(template, 'Template section')

    # 2. Mocking: Mock the external LLM call
    mock_resp = DummyResponse('Section A\nSection B')
    mocker.patch('litellm.completion', return_value=mock_resp)

    # 3. Execution: Run the agent's main function
    out_dir = tmp_path / 'out'
    path = agent.generate_full_protocol(str(synopsis), str(template), str(out_dir))
    
    # 4. Assertion: Verify a file was created
    assert Path(path).exists()

# Test for the checklist update utility function
def test_update_checklist(tmp_path):
    # 1. Setup: Create a mock checklist file
    checklist_data = [
        {'agentId': '1.400', 'name': 'Full Protocol Generation Agent', 'status': 0, 'dependencies': []}
    ]
    file_path = tmp_path / 'checklist.yml'
    file_path.write_text(yaml.safe_dump(checklist_data))

    # 2. Execution: Run the function
    agent.update_checklist(str(file_path), 90)

    # 3. Assertion: Verify the status was updated correctly
    updated_data = yaml.safe_load(file_path.read_text())
    assert updated_data[0]['status'] == 90

# Test for the progress logging utility function (IMPROVED)
def test_write_progress_log_creates_valid_json(tmp_path):
    # 1. Setup
    log_dir = tmp_path / 'logs'
    test_status = 50
    test_summary = "Partial work done"

    # 2. Execution
    path_str = agent.write_progress_log(str(log_dir), test_status, test_summary)
    
    # 3. Assertions
    log_path = Path(path_str)
    assert log_path.exists()
    assert log_path.name.startswith(f"1.400-{test_status}-")
    
    # 3a. NEW: Assert the content of the JSON file
    log_content = json.loads(log_path.read_text())
    assert log_content['agentId'] == '1.400'
    assert log_content['status'] == test_status
    assert log_content['summary'] == test_summary
    assert 'timestamp' in log_content # Verify the timestamp key exists
    assert len(log_content['timestamp']) > 10 # Verify the timestamp is a reasonable length

