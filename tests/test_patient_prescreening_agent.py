import pytest
import json
import os
from unittest.mock import Mock, patch

from scripts.patient_prescreening_agent import (
    load_screening_criteria,
    generate_screening_questions,
    interpret_response,
    conduct_screening_session,
    create_candidate_payload,
    send_to_secure_endpoint,
    save_screening_session,
    update_checklist,
    write_progress_log
)


@pytest.fixture
def mock_criteria():
    """Mock clinical trial criteria."""
    return {
        "inclusion": [
            "Age 18-65 years",
            "Diagnosed with condition X",
            "Able to provide informed consent"
        ],
        "exclusion": [
            "Pregnancy",
            "History of allergic reactions to study drug",
            "Severe kidney disease"
        ]
    }


@pytest.fixture
def mock_questions():
    """Mock screening questions."""
    return [
        {"question": "What is your age?", "type": "numeric"},
        {"question": "Do you have a history of diabetes?", "type": "boolean"},
        {"question": "Are you currently taking any medications?", "type": "text"}
    ]


@pytest.fixture
def mock_contact_info():
    """Mock contact information."""
    return {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "555-0123"
    }


def test_load_screening_criteria_success(tmp_path):
    """Test successful loading of screening criteria."""
    criteria_data = {"inclusion": ["Age 18+"], "exclusion": ["Pregnancy"]}
    criteria_file = tmp_path / "criteria.json"
    criteria_file.write_text(json.dumps(criteria_data))
    
    result = load_screening_criteria(str(criteria_file))
    assert result == criteria_data


def test_load_screening_criteria_file_not_found():
    """Test loading criteria when file doesn't exist."""
    result = load_screening_criteria("nonexistent.json")
    assert result == {}


def test_generate_screening_questions_success(mocker, mock_criteria):
    """Test successful generation of screening questions."""
    # Mock LLM model name
    mocker.patch('scripts.patient_prescreening_agent.get_llm_model_name', return_value='gpt-4')
    
    # Mock LLM response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    [
        {"question": "What is your age?", "type": "numeric"},
        {"question": "Do you have diabetes?", "type": "boolean"}
    ]
    '''
    mocker.patch('scripts.patient_prescreening_agent.completion', return_value=mock_response)
    
    questions = generate_screening_questions(mock_criteria)
    assert len(questions) == 2
    assert questions[0]["question"] == "What is your age?"
    assert questions[0]["type"] == "numeric"


def test_generate_screening_questions_no_model(mocker, mock_criteria):
    """Test question generation when LLM model is not configured."""
    mocker.patch('scripts.patient_prescreening_agent.get_llm_model_name', return_value=None)
    
    questions = generate_screening_questions(mock_criteria)
    assert questions == []


def test_interpret_response_success(mocker):
    """Test successful response interpretation."""
    mocker.patch('scripts.patient_prescreening_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "interpreted_value": true,
        "eligibility_impact": "eligible",
        "confidence": 0.95,
        "notes": "User confirmed diabetes diagnosis"
    }
    '''
    mocker.patch('scripts.patient_prescreening_agent.completion', return_value=mock_response)
    
    result = interpret_response("Do you have diabetes?", "yes", "boolean")
    assert result["interpreted_value"] == True
    assert result["eligibility_impact"] == "eligible"
    assert result["confidence"] == 0.95


def test_interpret_response_no_model(mocker):
    """Test response interpretation when LLM model is not configured."""
    mocker.patch('scripts.patient_prescreening_agent.get_llm_model_name', return_value=None)
    
    result = interpret_response("Do you have diabetes?", "yes", "boolean")
    assert result["interpreted_value"] == "yes"
    assert result["eligibility_impact"] == "unknown"


def test_conduct_screening_session_eligible(mocker, mock_questions):
    """Test screening session with eligible candidate."""
    responses = ["25", "no", "none"]
    
    # Mock interpret_response to return eligible for all questions
    def mock_interpret(question, response, q_type):
        return {
            "interpreted_value": response,
            "eligibility_impact": "eligible",
            "confidence": 0.9,
            "notes": "Meets criteria"
        }
    
    mocker.patch('scripts.patient_prescreening_agent.interpret_response', side_effect=mock_interpret)
    
    result = conduct_screening_session(mock_questions, responses)
    assert result["eligible"] == True
    assert len(result["screening_results"]) == 3
    assert result["ineligible_reasons"] == []


def test_conduct_screening_session_ineligible(mocker, mock_questions):
    """Test screening session with ineligible candidate."""
    responses = ["25", "yes", "warfarin"]
    
    # Mock interpret_response to return ineligible for second question
    def mock_interpret(question, response, q_type):
        if "diabetes" in question:
            return {
                "interpreted_value": True,
                "eligibility_impact": "ineligible",
                "confidence": 0.9,
                "notes": "Diabetes is exclusion criterion"
            }
        return {
            "interpreted_value": response,
            "eligibility_impact": "eligible",
            "confidence": 0.9,
            "notes": "Meets criteria"
        }
    
    mocker.patch('scripts.patient_prescreening_agent.interpret_response', side_effect=mock_interpret)
    
    result = conduct_screening_session(mock_questions, responses)
    assert result["eligible"] == False
    assert len(result["ineligible_reasons"]) == 1
    assert "Q2:" in result["ineligible_reasons"][0]


def test_conduct_screening_session_mismatch():
    """Test screening session with mismatched questions and responses."""
    questions = [{"question": "Age?", "type": "numeric"}]
    responses = ["25", "extra response"]
    
    result = conduct_screening_session(questions, responses)
    assert result["eligible"] == False
    assert result["reason"] == "Incomplete screening"


def test_create_candidate_payload_eligible(mock_contact_info):
    """Test payload creation for eligible candidate."""
    screening_result = {
        "eligible": True,
        "screening_results": [
            {
                "question": "What is your age?",
                "response": "25",
                "interpretation": {"interpreted_value": 25, "eligibility_impact": "eligible"}
            }
        ],
        "ineligible_reasons": [],
        "session_timestamp": "2024-01-01T12:00:00Z"
    }
    
    payload = create_candidate_payload(screening_result, mock_contact_info)
    assert payload["eligibility_status"] == "pre_screened_eligible"
    assert payload["contact_information"] == mock_contact_info
    assert payload["screening_summary"]["eligible"] == True
    assert payload["screening_summary"]["total_questions"] == 1


def test_create_candidate_payload_ineligible(mock_contact_info):
    """Test payload creation for ineligible candidate."""
    screening_result = {
        "eligible": False,
        "screening_results": [],
        "ineligible_reasons": ["Age requirement not met"],
        "session_timestamp": "2024-01-01T12:00:00Z"
    }
    
    payload = create_candidate_payload(screening_result, mock_contact_info)
    assert payload == {}


def test_send_to_secure_endpoint_success():
    """Test successful sending to secure endpoint."""
    payload = {"candidate_id": "test123", "status": "eligible"}
    endpoint_url = "https://example.com/secure/candidates"
    
    result = send_to_secure_endpoint(payload, endpoint_url)
    assert result == True


def test_save_screening_session(tmp_path):
    """Test saving screening session data."""
    session_data = {
        "questions": [{"question": "Age?", "type": "numeric"}],
        "responses": ["25"],
        "screening_result": {"eligible": True}
    }
    
    filepath = save_screening_session(session_data, str(tmp_path))
    assert os.path.exists(filepath)
    
    with open(filepath, "r") as f:
        saved_data = json.load(f)
    assert saved_data == session_data


def test_update_checklist(tmp_path):
    """Test updating checklist file."""
    checklist_data = [
        {"agentId": "2.300", "name": "Test Agent", "status": 0},
        {"agentId": "2.400", "name": "Other Agent", "status": 50}
    ]
    
    checklist_file = tmp_path / "checklist.yml"
    import yaml
    with open(checklist_file, "w") as f:
        yaml.safe_dump(checklist_data, f)
    
    update_checklist(str(checklist_file), 100)
    
    with open(checklist_file, "r") as f:
        updated_data = yaml.safe_load(f)
    
    assert updated_data[0]["status"] == 100
    assert updated_data[1]["status"] == 50  # Unchanged


def test_write_progress_log(tmp_path):
    """Test writing progress log."""
    log_path = write_progress_log(str(tmp_path), 100, "Test summary")
    
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log_data = json.load(f)
    
    assert log_data["agentId"] == "2.300"
    assert log_data["status"] == 100
    assert log_data["summary"] == "Test summary"
    assert "timestamp" in log_data