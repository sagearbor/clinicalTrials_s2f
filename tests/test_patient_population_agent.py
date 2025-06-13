import os
import sys
import json
import yaml
from pathlib import Path
import pytest
import datetime # Ensure datetime is imported

# Add project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts import patient_population_agent as agent

# --- ROBUST MOCKING CLASSES ---
class MockLLMMessage:
    def __init__(self, content):
        self.content = content

class MockLLMChoice:
    def __init__(self, content):
        self.message = MockLLMMessage(content)

class MockLLMResponse:
    def __init__(self, content=""):
        self.choices = [MockLLMChoice(content)]

# --- TESTS ---

def test_generate_report_creates_json(tmp_path, mocker):
    # 1. Setup: Define mock inputs and API responses
    input_data = {
        'inclusionCriteria': ['age > 50'],
        'exclusionCriteria': ['diabetes'],
        'geographies': ['US']
    }
    mock_counts = {'US': 100}
    
    # Mock both the external API and LLM calls
    mocker.patch('requests.post', return_value=mocker.Mock(json=lambda: mock_counts, raise_for_status=lambda: None))
    mocker.patch('litellm.completion', return_value=MockLLMResponse('Summary text'))

    # 2. Execution
    out_dir = tmp_path / 'output'
    path = agent.generate_report(input_data, str(out_dir), 'http://example.com')
    
    # 3. Assertions
    assert Path(path).exists()
    data = json.loads(Path(path).read_text())
    assert data['counts'] == mock_counts
    assert data['summary'] == 'Summary text'


def test_update_checklist(tmp_path):
    # 1. Setup
    checklist_data = [
        {'agentId': '1.200', 'name': 'Patient Population Analysis Agent', 'status': 0, 'dependencies': ['1.100']}
    ]
    file_path = tmp_path / 'checklist.yml'
    file_path.write_text(yaml.safe_dump(checklist_data))

    # 2. Execution
    agent.update_checklist(str(file_path), 80)

    # 3. Assertion
    updated_data = yaml.safe_load(file_path.read_text())
    assert updated_data[0]['status'] == 80


def test_write_progress_log_creates_valid_json(tmp_path):
    # 1. Setup
    log_dir = tmp_path / 'logs'
    test_status = 50
    test_summary = "Analyzed US and EU populations."

    # 2. Execution
    path_str = agent.write_progress_log(str(log_dir), test_status, test_summary)
    
    # 3. Assertions
    log_path = Path(path_str)
    assert log_path.exists()
    assert log_path.name.startswith(f"1.200-{test_status}-")
    
    # Assert the content of the JSON file
    log_content = json.loads(log_path.read_text())
    assert log_content['agentId'] == '1.200'
    assert log_content['status'] == test_status
    assert log_content['summary'] == test_summary
    assert 'timestamp' in log_content
    assert len(log_content['timestamp']) > 10
