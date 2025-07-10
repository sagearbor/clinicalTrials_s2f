import pytest
import json
import os
from unittest.mock import Mock, patch

from scripts.realtime_data_validation_agent import (
    ValidationRule,
    DataPoint,
    ValidationIssue,
    load_validation_plan,
    parse_edc_data,
    validate_range_check,
    validate_required_check,
    validate_logical_check,
    validate_format_check,
    run_validation_checks,
    create_data_queries,
    save_validation_report,
    update_checklist,
    write_progress_log
)


@pytest.fixture
def mock_validation_rules():
    """Mock validation rules for testing."""
    return [
        ValidationRule(
            rule_id="RULE_001",
            rule_type="range",
            field_name="age",
            description="Age must be between 18 and 65",
            parameters={"min": 18, "max": 65},
            severity="major"
        ),
        ValidationRule(
            rule_id="RULE_002",
            rule_type="required",
            field_name="subject_id",
            description="Subject ID is required",
            parameters={},
            severity="critical"
        ),
        ValidationRule(
            rule_id="RULE_003",
            rule_type="format",
            field_name="email",
            description="Email must be valid format",
            parameters={"pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"},
            severity="minor"
        )
    ]


@pytest.fixture
def mock_data_points():
    """Mock data points for testing."""
    return [
        DataPoint(
            subject_id="SUBJ001",
            visit_name="Visit 1",
            form_name="Demographics",
            field_name="age",
            value=25,
            timestamp="2024-01-01T10:00:00Z",
            data_type="numeric"
        ),
        DataPoint(
            subject_id="SUBJ002",
            visit_name="Visit 1",
            form_name="Demographics",
            field_name="age",
            value=70,  # Out of range
            timestamp="2024-01-01T10:00:00Z",
            data_type="numeric"
        ),
        DataPoint(
            subject_id="SUBJ003",
            visit_name="Visit 1",
            form_name="Demographics",
            field_name="subject_id",
            value="",  # Required field empty
            timestamp="2024-01-01T10:00:00Z",
            data_type="string"
        )
    ]


def test_load_validation_plan_success(tmp_path):
    """Test successful loading of validation plan."""
    plan_data = {
        "validation_rules": [
            {
                "rule_id": "RULE_001",
                "rule_type": "range",
                "field_name": "age",
                "description": "Age range check",
                "parameters": {"min": 18, "max": 65},
                "severity": "major"
            }
        ]
    }
    
    plan_file = tmp_path / "validation_plan.json"
    plan_file.write_text(json.dumps(plan_data))
    
    rules = load_validation_plan(str(plan_file))
    assert len(rules) == 1
    assert rules[0].rule_id == "RULE_001"
    assert rules[0].rule_type == "range"
    assert rules[0].parameters["min"] == 18


def test_load_validation_plan_file_not_found():
    """Test loading validation plan when file doesn't exist."""
    rules = load_validation_plan("nonexistent.json")
    assert rules == []


def test_parse_edc_data_from_file(tmp_path):
    """Test parsing EDC data from file."""
    edc_data = {
        "records": [
            {
                "subject_id": "SUBJ001",
                "visit_name": "Visit 1",
                "form_name": "Demographics",
                "fields": {
                    "age": 25,
                    "gender": "M"
                },
                "data_types": {
                    "age": "numeric",
                    "gender": "string"
                },
                "timestamp": "2024-01-01T10:00:00Z"
            }
        ]
    }
    
    data_file = tmp_path / "edc_data.json"
    data_file.write_text(json.dumps(edc_data))
    
    data_points = parse_edc_data(str(data_file))
    assert len(data_points) == 2
    assert data_points[0].subject_id == "SUBJ001"
    assert data_points[0].field_name == "age"
    assert data_points[0].value == 25


def test_parse_edc_data_from_dict():
    """Test parsing EDC data from dictionary."""
    edc_data = {
        "records": [
            {
                "subject_id": "SUBJ001",
                "visit_name": "Visit 1",
                "form_name": "Demographics",
                "fields": {
                    "age": 25
                },
                "timestamp": "2024-01-01T10:00:00Z"
            }
        ]
    }
    
    data_points = parse_edc_data(edc_data)
    assert len(data_points) == 1
    assert data_points[0].subject_id == "SUBJ001"


def test_validate_range_check_pass():
    """Test range validation that passes."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "age", 25, "2024-01-01T10:00:00Z", "numeric")
    rule = ValidationRule("RULE_001", "range", "age", "Age range", {"min": 18, "max": 65}, "major")
    
    issue = validate_range_check(data_point, rule)
    assert issue is None


def test_validate_range_check_fail_min():
    """Test range validation that fails minimum."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "age", 15, "2024-01-01T10:00:00Z", "numeric")
    rule = ValidationRule("RULE_001", "range", "age", "Age range", {"min": 18, "max": 65}, "major")
    
    issue = validate_range_check(data_point, rule)
    assert issue is not None
    assert issue.subject_id == "SUBJ001"
    assert "below minimum" in issue.issue_description


def test_validate_range_check_fail_max():
    """Test range validation that fails maximum."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "age", 70, "2024-01-01T10:00:00Z", "numeric")
    rule = ValidationRule("RULE_001", "range", "age", "Age range", {"min": 18, "max": 65}, "major")
    
    issue = validate_range_check(data_point, rule)
    assert issue is not None
    assert issue.subject_id == "SUBJ001"
    assert "above maximum" in issue.issue_description


def test_validate_range_check_non_numeric():
    """Test range validation with non-numeric value."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "age", "not_a_number", "2024-01-01T10:00:00Z", "numeric")
    rule = ValidationRule("RULE_001", "range", "age", "Age range", {"min": 18, "max": 65}, "major")
    
    issue = validate_range_check(data_point, rule)
    assert issue is not None
    assert "Non-numeric value" in issue.issue_description


def test_validate_required_check_pass():
    """Test required validation that passes."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "subject_id", "SUBJ001", "2024-01-01T10:00:00Z", "string")
    rule = ValidationRule("RULE_002", "required", "subject_id", "Subject ID required", {}, "critical")
    
    issue = validate_required_check(data_point, rule)
    assert issue is None


def test_validate_required_check_fail_empty():
    """Test required validation that fails with empty value."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "subject_id", "", "2024-01-01T10:00:00Z", "string")
    rule = ValidationRule("RULE_002", "required", "subject_id", "Subject ID required", {}, "critical")
    
    issue = validate_required_check(data_point, rule)
    assert issue is not None
    assert issue.severity == "critical"
    assert "missing or empty" in issue.issue_description


def test_validate_required_check_fail_none():
    """Test required validation that fails with None value."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "subject_id", None, "2024-01-01T10:00:00Z", "string")
    rule = ValidationRule("RULE_002", "required", "subject_id", "Subject ID required", {}, "critical")
    
    issue = validate_required_check(data_point, rule)
    assert issue is not None
    assert "missing or empty" in issue.issue_description


def test_validate_format_check_pass():
    """Test format validation that passes."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Contact", "email", "test@example.com", "2024-01-01T10:00:00Z", "string")
    rule = ValidationRule("RULE_003", "format", "email", "Email format", {"pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"}, "minor")
    
    issue = validate_format_check(data_point, rule)
    assert issue is None


def test_validate_format_check_fail():
    """Test format validation that fails."""
    data_point = DataPoint("SUBJ001", "Visit 1", "Contact", "email", "invalid_email", "2024-01-01T10:00:00Z", "string")
    rule = ValidationRule("RULE_003", "format", "email", "Email format", {"pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"}, "minor")
    
    issue = validate_format_check(data_point, rule)
    assert issue is not None
    assert "does not match required format" in issue.issue_description


def test_validate_logical_check_success(mocker):
    """Test logical validation with LLM."""
    mocker.patch('scripts.realtime_data_validation_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "violation_found": true,
        "issue_description": "Age and birth date are inconsistent",
        "suggested_action": "Verify birth date calculation",
        "confidence": 0.9
    }
    '''
    mocker.patch('scripts.realtime_data_validation_agent.completion', return_value=mock_response)
    
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "age", 25, "2024-01-01T10:00:00Z", "numeric")
    rule = ValidationRule("RULE_004", "logical", "age", "Age consistency check", {"check_birth_date": True}, "major")
    all_data = [data_point]
    
    issue = validate_logical_check(data_point, rule, all_data)
    assert issue is not None
    assert issue.severity == "major"
    assert "inconsistent" in issue.issue_description


def test_validate_logical_check_no_model(mocker):
    """Test logical validation when no LLM model is available."""
    mocker.patch('scripts.realtime_data_validation_agent.get_llm_model_name', return_value=None)
    
    data_point = DataPoint("SUBJ001", "Visit 1", "Demographics", "age", 25, "2024-01-01T10:00:00Z", "numeric")
    rule = ValidationRule("RULE_004", "logical", "age", "Age consistency check", {}, "major")
    all_data = [data_point]
    
    issue = validate_logical_check(data_point, rule, all_data)
    assert issue is None


def test_run_validation_checks(mock_data_points, mock_validation_rules):
    """Test running validation checks on multiple data points."""
    issues = run_validation_checks(mock_data_points, mock_validation_rules)
    
    # Should find issues for out-of-range age and empty required field
    assert len(issues) >= 2
    
    # Check that we have the expected issue types
    issue_descriptions = [issue.issue_description for issue in issues]
    assert any("above maximum" in desc for desc in issue_descriptions)
    assert any("missing or empty" in desc for desc in issue_descriptions)


def test_create_data_queries(tmp_path):
    """Test creating data queries from validation issues."""
    issues = [
        ValidationIssue(
            issue_id="ISSUE_001",
            rule_id="RULE_001",
            subject_id="SUBJ001",
            field_name="age",
            issue_description="Age out of range",
            severity="major",
            suggested_action="Verify age value",
            timestamp="2024-01-01T10:00:00Z"
        )
    ]
    
    queries = create_data_queries(issues, str(tmp_path))
    assert len(queries) == 1
    assert queries[0]["query_id"] == "DQ_ISSUE_001"
    assert queries[0]["subject_id"] == "SUBJ001"
    assert queries[0]["priority"] == "major"
    
    # Check that file was created
    query_files = list(tmp_path.glob("data_queries_*.json"))
    assert len(query_files) == 1


def test_save_validation_report(tmp_path, mock_data_points):
    """Test saving validation report."""
    issues = [
        ValidationIssue(
            issue_id="ISSUE_001",
            rule_id="RULE_001",
            subject_id="SUBJ001",
            field_name="age",
            issue_description="Age out of range",
            severity="major",
            suggested_action="Verify age value",
            timestamp="2024-01-01T10:00:00Z"
        )
    ]
    
    report_file = save_validation_report(mock_data_points, issues, str(tmp_path))
    
    assert os.path.exists(report_file)
    with open(report_file, "r") as f:
        report = json.load(f)
    
    assert report["validation_summary"]["total_data_points"] == len(mock_data_points)
    assert report["validation_summary"]["total_issues"] == len(issues)
    assert report["validation_summary"]["major_issues"] == 1
    assert len(report["issues"]) == 1


def test_update_checklist(tmp_path):
    """Test updating checklist file."""
    checklist_data = [
        {"agentId": "3.100", "name": "Real-time Data Validation Agent", "status": 0},
        {"agentId": "3.200", "name": "Other Agent", "status": 50}
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
    log_path = write_progress_log(str(tmp_path), 100, "Data validation completed")
    
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log_data = json.load(f)
    
    assert log_data["agentId"] == "3.100"
    assert log_data["status"] == 100
    assert log_data["summary"] == "Data validation completed"
    assert "timestamp" in log_data


def test_validation_rule_creation():
    """Test ValidationRule dataclass creation."""
    rule = ValidationRule(
        rule_id="TEST_001",
        rule_type="range",
        field_name="age",
        description="Age validation",
        parameters={"min": 18, "max": 65},
        severity="major"
    )
    
    assert rule.rule_id == "TEST_001"
    assert rule.rule_type == "range"
    assert rule.parameters["min"] == 18


def test_data_point_creation():
    """Test DataPoint dataclass creation."""
    data_point = DataPoint(
        subject_id="SUBJ001",
        visit_name="Visit 1",
        form_name="Demographics",
        field_name="age",
        value=25,
        timestamp="2024-01-01T10:00:00Z",
        data_type="numeric"
    )
    
    assert data_point.subject_id == "SUBJ001"
    assert data_point.value == 25
    assert data_point.data_type == "numeric"


def test_validation_issue_creation():
    """Test ValidationIssue dataclass creation."""
    issue = ValidationIssue(
        issue_id="ISSUE_001",
        rule_id="RULE_001",
        subject_id="SUBJ001",
        field_name="age",
        issue_description="Age out of range",
        severity="major",
        suggested_action="Verify age",
        timestamp="2024-01-01T10:00:00Z"
    )
    
    assert issue.issue_id == "ISSUE_001"
    assert issue.severity == "major"
    assert "range" in issue.issue_description