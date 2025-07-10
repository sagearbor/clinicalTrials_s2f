import pytest
import json
import os
from unittest.mock import Mock, patch

from scripts.pharmacovigilance_agent import (
    AlertSeverity,
    DataSource,
    SafetyRule,
    DataEntry,
    SafetyEvent,
    SafetyAlert,
    load_safety_rules,
    parse_data_streams,
    detect_safety_events,
    generate_safety_narrative,
    create_safety_alerts,
    send_alert_email,
    send_alert_sms,
    dispatch_alerts,
    save_safety_events,
    save_safety_alerts,
    update_checklist,
    write_progress_log
)


@pytest.fixture
def mock_safety_rules():
    """Mock safety rules for testing."""
    return [
        SafetyRule(
            rule_id="SAE_001",
            name="Serious Adverse Event",
            keywords=["death", "hospitalization", "life-threatening"],
            patterns=[r"serious\s+adverse\s+event", r"sae"],
            severity=AlertSeverity.CRITICAL,
            description="Serious adverse event detection",
            immediate_alert=True
        ),
        SafetyRule(
            rule_id="AE_001",
            name="Adverse Event",
            keywords=["headache", "nausea", "dizziness"],
            patterns=[r"adverse\s+event", r"side\s+effect"],
            severity=AlertSeverity.MEDIUM,
            description="Adverse event detection",
            immediate_alert=False
        )
    ]


@pytest.fixture
def mock_data_entries():
    """Mock data entries for testing."""
    return [
        DataEntry(
            entry_id="EDC_001",
            source=DataSource.EDC,
            subject_id="SUBJ001",
            timestamp="2024-01-01T10:00:00Z",
            content="Patient experienced severe headache and nausea after treatment",
            metadata={"visit": "Day 1", "form": "Adverse Events"}
        ),
        DataEntry(
            entry_id="APP_001",
            source=DataSource.PATIENT_APP,
            subject_id="SUBJ002",
            timestamp="2024-01-01T11:00:00Z",
            content="Patient reported hospitalization due to serious adverse event",
            metadata={"app_version": "1.0", "device": "mobile"}
        ),
        DataEntry(
            entry_id="CALL_001",
            source=DataSource.CALL_CENTER,
            subject_id="SUBJ003",
            timestamp="2024-01-01T12:00:00Z",
            content="Call from patient about mild dizziness",
            metadata={"call_duration": "5 minutes", "agent": "Agent123"}
        )
    ]


@pytest.fixture
def mock_safety_events():
    """Mock safety events for testing."""
    return [
        SafetyEvent(
            event_id="SE_001",
            rule_id="SAE_001",
            subject_id="SUBJ001",
            event_type="Serious Adverse Event",
            description="Potential SAE detected",
            severity=AlertSeverity.CRITICAL,
            source=DataSource.EDC,
            timestamp="2024-01-01T10:00:00Z",
            confidence=0.9,
            raw_data="Patient experienced severe complications"
        )
    ]


def test_load_safety_rules_success(tmp_path):
    """Test successful loading of safety rules."""
    rules_data = {
        "safety_rules": [
            {
                "rule_id": "SAE_001",
                "name": "Serious Adverse Event",
                "keywords": ["death", "hospitalization"],
                "patterns": [r"serious\s+adverse\s+event"],
                "severity": "critical",
                "description": "SAE detection",
                "immediate_alert": True
            }
        ]
    }
    
    rules_file = tmp_path / "safety_rules.json"
    rules_file.write_text(json.dumps(rules_data))
    
    rules = load_safety_rules(str(rules_file))
    assert len(rules) == 1
    assert rules[0].rule_id == "SAE_001"
    assert rules[0].severity == AlertSeverity.CRITICAL
    assert rules[0].immediate_alert == True


def test_load_safety_rules_file_not_found():
    """Test loading safety rules when file doesn't exist."""
    rules = load_safety_rules("nonexistent.json")
    assert rules == []


def test_parse_data_streams_from_dict():
    """Test parsing data streams from dictionary."""
    data_sources = {
        "edc": {
            "records": [
                {
                    "entry_id": "EDC_001",
                    "subject_id": "SUBJ001",
                    "content": "Patient experienced headache",
                    "timestamp": "2024-01-01T10:00:00Z",
                    "metadata": {"visit": "Day 1"}
                }
            ]
        }
    }
    
    entries = parse_data_streams(data_sources)
    assert len(entries) == 1
    assert entries[0].source == DataSource.EDC
    assert entries[0].subject_id == "SUBJ001"
    assert "headache" in entries[0].content


def test_parse_data_streams_from_file(tmp_path):
    """Test parsing data streams from file."""
    data_content = {
        "records": [
            {
                "entry_id": "EDC_001",
                "subject_id": "SUBJ001",
                "content": "Patient experienced headache",
                "timestamp": "2024-01-01T10:00:00Z"
            }
        ]
    }
    
    data_file = tmp_path / "edc_data.json"
    data_file.write_text(json.dumps(data_content))
    
    data_sources = {"edc": str(data_file)}
    entries = parse_data_streams(data_sources)
    assert len(entries) == 1
    assert entries[0].source == DataSource.EDC


def test_detect_safety_events_keyword_match(mock_data_entries, mock_safety_rules):
    """Test safety event detection with keyword matching."""
    events = detect_safety_events(mock_data_entries, mock_safety_rules)
    
    # Should detect events for headache/nausea and hospitalization
    assert len(events) >= 2
    
    # Check that events have proper structure
    for event in events:
        assert event.event_id is not None
        assert event.confidence > 0
        assert event.severity in [AlertSeverity.CRITICAL, AlertSeverity.MEDIUM]


def test_detect_safety_events_no_matches():
    """Test safety event detection with no matches."""
    data_entries = [
        DataEntry(
            entry_id="TEST_001",
            source=DataSource.EDC,
            subject_id="SUBJ001",
            timestamp="2024-01-01T10:00:00Z",
            content="Patient doing well, no issues reported",
            metadata={}
        )
    ]
    
    rules = [
        SafetyRule(
            rule_id="TEST_RULE",
            name="Test Rule",
            keywords=["emergency", "critical"],
            patterns=[r"urgent\s+care"],
            severity=AlertSeverity.HIGH,
            description="Test rule",
            immediate_alert=False
        )
    ]
    
    events = detect_safety_events(data_entries, rules)
    assert len(events) == 0


def test_generate_safety_narrative_with_llm(mocker, mock_safety_events):
    """Test safety narrative generation with LLM."""
    mocker.patch('scripts.pharmacovigilance_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """
    SAFETY EVENT NARRATIVE:
    
    A critical safety event has been detected for Subject SUBJ001. The event involves potential serious adverse event symptoms that require immediate medical attention and regulatory notification.
    
    Clinical Significance: High priority event requiring immediate investigation.
    
    Recommended Actions:
    1. Immediate medical evaluation of the subject
    2. Notify principal investigator
    3. Prepare SAE report for regulatory submission
    
    Urgency: CRITICAL - Action required within 24 hours.
    """
    mocker.patch('scripts.pharmacovigilance_agent.completion', return_value=mock_response)
    
    narrative = generate_safety_narrative(mock_safety_events[0], {"context": "test"})
    assert "SAFETY EVENT NARRATIVE" in narrative
    assert "CRITICAL" in narrative
    assert "Subject SUBJ001" in narrative


def test_generate_safety_narrative_no_llm(mocker, mock_safety_events):
    """Test safety narrative generation without LLM."""
    mocker.patch('scripts.pharmacovigilance_agent.get_llm_model_name', return_value=None)
    
    narrative = generate_safety_narrative(mock_safety_events[0], {})
    assert "safety event" in narrative.lower()
    assert "SUBJ001" in narrative


def test_create_safety_alerts(mocker, mock_safety_events):
    """Test creating safety alerts from events."""
    mocker.patch('scripts.pharmacovigilance_agent.generate_safety_narrative', return_value="Test narrative")
    
    alert_config = {
        "recipients": {
            "critical": ["safety@example.com"],
            "high": ["safety@example.com"],
            "medium": ["safety@example.com"],
            "low": ["safety@example.com"]
        },
        "delivery_methods": {
            "critical": ["email", "sms"],
            "high": ["email"],
            "medium": ["email"],
            "low": ["email"]
        }
    }
    
    alerts = create_safety_alerts(mock_safety_events, alert_config)
    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.CRITICAL
    assert alerts[0].narrative == "Test narrative"
    assert "email" in alerts[0].delivery_methods
    assert "sms" in alerts[0].delivery_methods


def test_send_alert_email():
    """Test sending email alerts."""
    alert = SafetyAlert(
        alert_id="ALERT_001",
        event_id="SE_001",
        subject_id="SUBJ001",
        alert_type="Safety Alert",
        severity=AlertSeverity.CRITICAL,
        narrative="Test narrative",
        recipients=["safety@example.com"],
        delivery_methods=["email"],
        timestamp="2024-01-01T10:00:00Z"
    )
    
    result = send_alert_email(alert, {})
    assert result == True  # Mock implementation always returns True


def test_send_alert_sms():
    """Test sending SMS alerts."""
    alert = SafetyAlert(
        alert_id="ALERT_001",
        event_id="SE_001",
        subject_id="SUBJ001",
        alert_type="Safety Alert",
        severity=AlertSeverity.CRITICAL,
        narrative="Test narrative",
        recipients=["+1234567890"],
        delivery_methods=["sms"],
        timestamp="2024-01-01T10:00:00Z"
    )
    
    result = send_alert_sms(alert, {})
    assert result == True  # Mock implementation always returns True


def test_dispatch_alerts():
    """Test dispatching multiple alerts."""
    alerts = [
        SafetyAlert(
            alert_id="ALERT_001",
            event_id="SE_001",
            subject_id="SUBJ001",
            alert_type="Safety Alert",
            severity=AlertSeverity.CRITICAL,
            narrative="Test narrative",
            recipients=["safety@example.com"],
            delivery_methods=["email", "sms"],
            timestamp="2024-01-01T10:00:00Z"
        ),
        SafetyAlert(
            alert_id="ALERT_002",
            event_id="SE_002",
            subject_id="SUBJ002",
            alert_type="Safety Alert",
            severity=AlertSeverity.MEDIUM,
            narrative="Test narrative",
            recipients=["safety@example.com"],
            delivery_methods=["email"],
            timestamp="2024-01-01T10:00:00Z"
        )
    ]
    
    notification_config = {}
    results = dispatch_alerts(alerts, notification_config)
    
    assert results["email"] == 2  # Both alerts sent via email
    assert results["sms"] == 1   # Only critical alert sent via SMS
    assert results["failed"] == 0


def test_save_safety_events(tmp_path, mock_safety_events):
    """Test saving safety events to file."""
    events_file = save_safety_events(mock_safety_events, str(tmp_path))
    
    assert os.path.exists(events_file)
    with open(events_file, "r") as f:
        saved_events = json.load(f)
    
    assert len(saved_events) == 1
    assert saved_events[0]["event_id"] == "SE_001"
    assert saved_events[0]["severity"] == "critical"


def test_save_safety_alerts(tmp_path):
    """Test saving safety alerts to file."""
    alerts = [
        SafetyAlert(
            alert_id="ALERT_001",
            event_id="SE_001",
            subject_id="SUBJ001",
            alert_type="Safety Alert",
            severity=AlertSeverity.CRITICAL,
            narrative="Test narrative",
            recipients=["safety@example.com"],
            delivery_methods=["email"],
            timestamp="2024-01-01T10:00:00Z"
        )
    ]
    
    alerts_file = save_safety_alerts(alerts, str(tmp_path))
    
    assert os.path.exists(alerts_file)
    with open(alerts_file, "r") as f:
        saved_alerts = json.load(f)
    
    assert len(saved_alerts) == 1
    assert saved_alerts[0]["alert_id"] == "ALERT_001"
    assert saved_alerts[0]["severity"] == "critical"


def test_update_checklist(tmp_path):
    """Test updating checklist file."""
    checklist_data = [
        {"agentId": "3.300", "name": "Pharmacovigilance Agent", "status": 0},
        {"agentId": "3.400", "name": "Other Agent", "status": 50}
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
    log_path = write_progress_log(str(tmp_path), 100, "Safety monitoring completed")
    
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log_data = json.load(f)
    
    assert log_data["agentId"] == "3.300"
    assert log_data["status"] == 100
    assert log_data["summary"] == "Safety monitoring completed"
    assert "timestamp" in log_data


def test_safety_rule_creation():
    """Test SafetyRule dataclass creation."""
    rule = SafetyRule(
        rule_id="TEST_001",
        name="Test Rule",
        keywords=["test", "keyword"],
        patterns=[r"test\s+pattern"],
        severity=AlertSeverity.HIGH,
        description="Test rule description",
        immediate_alert=True
    )
    
    assert rule.rule_id == "TEST_001"
    assert rule.severity == AlertSeverity.HIGH
    assert rule.immediate_alert == True
    assert len(rule.keywords) == 2


def test_data_entry_creation():
    """Test DataEntry dataclass creation."""
    entry = DataEntry(
        entry_id="TEST_001",
        source=DataSource.EDC,
        subject_id="SUBJ001",
        timestamp="2024-01-01T10:00:00Z",
        content="Test content",
        metadata={"key": "value"}
    )
    
    assert entry.entry_id == "TEST_001"
    assert entry.source == DataSource.EDC
    assert entry.metadata["key"] == "value"


def test_safety_event_creation():
    """Test SafetyEvent dataclass creation."""
    event = SafetyEvent(
        event_id="SE_001",
        rule_id="RULE_001",
        subject_id="SUBJ001",
        event_type="Test Event",
        description="Test description",
        severity=AlertSeverity.CRITICAL,
        source=DataSource.EDC,
        timestamp="2024-01-01T10:00:00Z",
        confidence=0.9,
        raw_data="Test raw data"
    )
    
    assert event.event_id == "SE_001"
    assert event.severity == AlertSeverity.CRITICAL
    assert event.confidence == 0.9


def test_safety_alert_creation():
    """Test SafetyAlert dataclass creation."""
    alert = SafetyAlert(
        alert_id="ALERT_001",
        event_id="SE_001",
        subject_id="SUBJ001",
        alert_type="Test Alert",
        severity=AlertSeverity.CRITICAL,
        narrative="Test narrative",
        recipients=["test@example.com"],
        delivery_methods=["email"],
        timestamp="2024-01-01T10:00:00Z"
    )
    
    assert alert.alert_id == "ALERT_001"
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.recipients == ["test@example.com"]