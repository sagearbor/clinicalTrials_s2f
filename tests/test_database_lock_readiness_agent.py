import pytest
import json
import os
from unittest.mock import Mock, patch

from scripts.database_lock_readiness_agent import (
    ActivityStatus,
    ActivityCategory,
    CloseoutActivity,
    QueryStatus,
    SafetyEventStatus,
    MonitoringVisitStatus,
    ReadinessAssessment,
    load_closeout_activities,
    analyze_query_status,
    analyze_safety_event_status,
    analyze_monitoring_visit_status,
    update_activity_status,
    calculate_readiness_assessment,
    generate_recommendations,
    create_readiness_dashboard,
    update_checklist,
    write_progress_log
)


@pytest.fixture
def mock_closeout_activities():
    """Mock closeout activities for testing."""
    return [
        CloseoutActivity(
            activity_id="ACT_001",
            name="Data Query Resolution",
            description="Resolve all outstanding data queries",
            category=ActivityCategory.DATA_QUERIES,
            status=ActivityStatus.IN_PROGRESS,
            completion_percentage=75.0,
            estimated_days_remaining=5,
            dependencies=[],
            assigned_to="Data Manager",
            priority="critical",
            last_updated="2024-01-01T10:00:00Z",
            notes="3 critical queries remaining"
        ),
        CloseoutActivity(
            activity_id="ACT_002",
            name="Safety Event Reconciliation",
            description="Complete safety event reconciliation",
            category=ActivityCategory.SAFETY_EVENTS,
            status=ActivityStatus.IN_PROGRESS,
            completion_percentage=80.0,
            estimated_days_remaining=3,
            dependencies=["ACT_001"],
            assigned_to="Safety Manager",
            priority="high",
            last_updated="2024-01-01T10:00:00Z",
            notes="2 SAEs pending review"
        ),
        CloseoutActivity(
            activity_id="ACT_003",
            name="Final Monitoring Visits",
            description="Complete final monitoring visits",
            category=ActivityCategory.MONITORING_VISITS,
            status=ActivityStatus.COMPLETED,
            completion_percentage=100.0,
            estimated_days_remaining=0,
            dependencies=[],
            assigned_to="CRA",
            priority="medium",
            last_updated="2024-01-01T10:00:00Z",
            notes="All visits completed"
        )
    ]


@pytest.fixture
def mock_query_status():
    """Mock query status for testing."""
    return QueryStatus(
        total_queries=100,
        open_queries=25,
        closed_queries=75,
        overdue_queries=5,
        avg_resolution_days=3.5,
        critical_queries=3
    )


@pytest.fixture
def mock_safety_status():
    """Mock safety event status for testing."""
    return SafetyEventStatus(
        total_events=50,
        reconciled_events=40,
        pending_events=10,
        serious_events=5,
        resolved_events=40,
        avg_resolution_days=7.0
    )


@pytest.fixture
def mock_monitoring_status():
    """Mock monitoring visit status for testing."""
    return MonitoringVisitStatus(
        total_sites=20,
        completed_visits=18,
        pending_visits=2,
        overdue_visits=1,
        avg_visit_duration=2.5,
        critical_findings=1
    )


def test_load_closeout_activities_success(tmp_path):
    """Test successful loading of closeout activities."""
    activities_data = {
        "closeout_activities": [
            {
                "activity_id": "ACT_001",
                "name": "Data Query Resolution",
                "description": "Resolve all data queries",
                "category": "data_queries",
                "status": "in_progress",
                "completion_percentage": 75.0,
                "estimated_days_remaining": 5,
                "dependencies": [],
                "assigned_to": "Data Manager",
                "priority": "critical",
                "last_updated": "2024-01-01T10:00:00Z",
                "notes": "3 queries remaining"
            }
        ]
    }
    
    activities_file = tmp_path / "activities.json"
    activities_file.write_text(json.dumps(activities_data))
    
    activities = load_closeout_activities(str(activities_file))
    assert len(activities) == 1
    assert activities[0].activity_id == "ACT_001"
    assert activities[0].category == ActivityCategory.DATA_QUERIES
    assert activities[0].status == ActivityStatus.IN_PROGRESS
    assert activities[0].completion_percentage == 75.0


def test_load_closeout_activities_file_not_found():
    """Test loading activities when file doesn't exist."""
    activities = load_closeout_activities("nonexistent.json")
    assert activities == []


def test_analyze_query_status_from_dict():
    """Test analyzing query status from dictionary."""
    query_data = {
        "queries": [
            {"status": "open", "priority": "critical", "overdue": True},
            {"status": "closed", "resolution_days": 5},
            {"status": "open", "priority": "medium", "overdue": False},
            {"status": "closed", "resolution_days": 3}
        ]
    }
    
    status = analyze_query_status(query_data)
    assert status.total_queries == 4
    assert status.open_queries == 2
    assert status.closed_queries == 2
    assert status.overdue_queries == 1
    assert status.critical_queries == 1
    assert status.avg_resolution_days == 4.0


def test_analyze_query_status_from_file(tmp_path):
    """Test analyzing query status from file."""
    query_data = {
        "queries": [
            {"status": "open", "priority": "critical"},
            {"status": "closed", "resolution_days": 5}
        ]
    }
    
    query_file = tmp_path / "queries.json"
    query_file.write_text(json.dumps(query_data))
    
    status = analyze_query_status(str(query_file))
    assert status.total_queries == 2
    assert status.open_queries == 1
    assert status.closed_queries == 1


def test_analyze_safety_event_status():
    """Test analyzing safety event status."""
    safety_data = {
        "safety_events": [
            {"reconciled": True, "status": "resolved", "serious": True, "resolution_days": 10},
            {"reconciled": False, "status": "pending", "serious": False},
            {"reconciled": True, "status": "resolved", "serious": False, "resolution_days": 5}
        ]
    }
    
    status = analyze_safety_event_status(safety_data)
    assert status.total_events == 3
    assert status.reconciled_events == 2
    assert status.pending_events == 1
    assert status.serious_events == 1
    assert status.resolved_events == 2
    assert status.avg_resolution_days == 7.5


def test_analyze_monitoring_visit_status():
    """Test analyzing monitoring visit status."""
    monitoring_data = {
        "sites": [{"site_id": "001"}, {"site_id": "002"}, {"site_id": "003"}],
        "monitoring_visits": [
            {"status": "completed", "duration_days": 3, "critical_findings": 0},
            {"status": "pending", "overdue": True},
            {"status": "completed", "duration_days": 2, "critical_findings": 1}
        ]
    }
    
    status = analyze_monitoring_visit_status(monitoring_data)
    assert status.total_sites == 3
    assert status.completed_visits == 2
    assert status.pending_visits == 1
    assert status.overdue_visits == 1
    assert status.critical_findings == 1
    assert status.avg_visit_duration == 2.5


def test_update_activity_status_data_queries(mock_closeout_activities, mock_query_status):
    """Test updating activity status for data queries."""
    status_data = {"query_status": mock_query_status}
    
    updated_activities = update_activity_status(mock_closeout_activities, status_data)
    
    # Find the data query activity
    dq_activity = next(a for a in updated_activities if a.category == ActivityCategory.DATA_QUERIES)
    assert dq_activity.status == ActivityStatus.IN_PROGRESS
    assert dq_activity.completion_percentage == 75.0  # closed_queries / total_queries * 100
    assert dq_activity.estimated_days_remaining > 0


def test_update_activity_status_safety_events(mock_closeout_activities, mock_safety_status):
    """Test updating activity status for safety events."""
    status_data = {"safety_status": mock_safety_status}
    
    updated_activities = update_activity_status(mock_closeout_activities, status_data)
    
    # Find the safety events activity
    se_activity = next(a for a in updated_activities if a.category == ActivityCategory.SAFETY_EVENTS)
    assert se_activity.status == ActivityStatus.IN_PROGRESS
    assert se_activity.completion_percentage == 80.0  # resolved_events / total_events * 100
    assert se_activity.estimated_days_remaining > 0


def test_update_activity_status_monitoring_visits(mock_closeout_activities, mock_monitoring_status):
    """Test updating activity status for monitoring visits."""
    status_data = {"monitoring_status": mock_monitoring_status}
    
    updated_activities = update_activity_status(mock_closeout_activities, status_data)
    
    # Find the monitoring visits activity
    mv_activity = next(a for a in updated_activities if a.category == ActivityCategory.MONITORING_VISITS)
    assert mv_activity.status == ActivityStatus.IN_PROGRESS
    assert mv_activity.completion_percentage == 90.0  # completed_visits / total_sites * 100


def test_calculate_readiness_assessment(mocker, mock_closeout_activities):
    """Test calculating readiness assessment."""
    mocker.patch('scripts.database_lock_readiness_agent.generate_recommendations', 
                 return_value=["Recommendation 1", "Recommendation 2"])
    
    status_data = {
        "query_status": QueryStatus(100, 10, 90, 2, 3.0, 1),
        "safety_status": SafetyEventStatus(50, 45, 5, 2, 45, 5.0),
        "monitoring_status": MonitoringVisitStatus(20, 19, 1, 0, 2.0, 0)
    }
    
    assessment = calculate_readiness_assessment(mock_closeout_activities, status_data)
    
    assert isinstance(assessment.overall_readiness_percentage, float)
    assert assessment.projected_lock_date is not None
    assert assessment.confidence_level in ["low", "medium", "high"]
    assert len(assessment.recommendations) == 2
    assert len(assessment.risk_factors) >= 0


def test_calculate_readiness_assessment_with_blockers(mock_closeout_activities):
    """Test readiness assessment with critical blockers."""
    # Add a blocked critical activity
    mock_closeout_activities[0].status = ActivityStatus.BLOCKED
    mock_closeout_activities[0].priority = "critical"
    mock_closeout_activities[0].notes = "Waiting for data clarification"
    
    status_data = {}
    assessment = calculate_readiness_assessment(mock_closeout_activities, status_data)
    
    assert len(assessment.critical_blockers) > 0
    assert "Waiting for data clarification" in assessment.critical_blockers[0]


def test_generate_recommendations_with_llm(mocker, mock_closeout_activities):
    """Test generating recommendations with LLM."""
    mocker.patch('scripts.database_lock_readiness_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "recommendations": [
            "Prioritize resolution of critical data queries",
            "Accelerate safety event reconciliation",
            "Complete final monitoring visits",
            "Review database lock checklist"
        ]
    }
    '''
    mocker.patch('scripts.database_lock_readiness_agent.completion', return_value=mock_response)
    
    recommendations = generate_recommendations(mock_closeout_activities, {})
    assert len(recommendations) == 4
    assert "critical data queries" in recommendations[0]


def test_generate_recommendations_no_llm(mocker, mock_closeout_activities):
    """Test generating recommendations without LLM."""
    mocker.patch('scripts.database_lock_readiness_agent.get_llm_model_name', return_value=None)
    
    recommendations = generate_recommendations(mock_closeout_activities, {})
    assert len(recommendations) >= 3
    assert any("blocked" in rec.lower() or "critical" in rec.lower() for rec in recommendations)


def test_create_readiness_dashboard(tmp_path, mock_closeout_activities):
    """Test creating readiness dashboard."""
    assessment = ReadinessAssessment(
        overall_readiness_percentage=85.0,
        projected_lock_date="2024-02-01",
        critical_blockers=[],
        risk_factors=["2 overdue queries"],
        recommendations=["Complete queries", "Review safety events"],
        confidence_level="medium"
    )
    
    status_data = {
        "query_status": QueryStatus(100, 10, 90, 2, 3.0, 1),
        "safety_status": SafetyEventStatus(50, 45, 5, 2, 45, 5.0),
        "monitoring_status": MonitoringVisitStatus(20, 19, 1, 0, 2.0, 0)
    }
    
    dashboard_file = create_readiness_dashboard(assessment, mock_closeout_activities, status_data, str(tmp_path))
    
    assert os.path.exists(dashboard_file)
    with open(dashboard_file, "r") as f:
        dashboard_data = json.load(f)
    
    assert dashboard_data["readiness_assessment"]["overall_readiness_percentage"] == 85.0
    assert dashboard_data["readiness_assessment"]["projected_lock_date"] == "2024-02-01"
    assert dashboard_data["activity_summary"]["total_activities"] == 3
    assert len(dashboard_data["activities"]) == 3
    assert "category_breakdown" in dashboard_data


def test_update_checklist(tmp_path):
    """Test updating checklist file."""
    checklist_data = [
        {"agentId": "4.100", "name": "Database Lock Readiness Agent", "status": 0},
        {"agentId": "4.200", "name": "Other Agent", "status": 50}
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
    log_path = write_progress_log(str(tmp_path), 100, "Database lock readiness assessment completed")
    
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log_data = json.load(f)
    
    assert log_data["agentId"] == "4.100"
    assert log_data["status"] == 100
    assert log_data["summary"] == "Database lock readiness assessment completed"
    assert "timestamp" in log_data


def test_closeout_activity_creation():
    """Test CloseoutActivity dataclass creation."""
    activity = CloseoutActivity(
        activity_id="TEST_001",
        name="Test Activity",
        description="Test description",
        category=ActivityCategory.DATA_QUERIES,
        status=ActivityStatus.IN_PROGRESS,
        completion_percentage=50.0,
        estimated_days_remaining=5,
        dependencies=["DEP_001"],
        assigned_to="Test User",
        priority="high",
        last_updated="2024-01-01T10:00:00Z",
        notes="Test notes"
    )
    
    assert activity.activity_id == "TEST_001"
    assert activity.category == ActivityCategory.DATA_QUERIES
    assert activity.status == ActivityStatus.IN_PROGRESS
    assert activity.completion_percentage == 50.0
    assert activity.dependencies == ["DEP_001"]


def test_query_status_creation():
    """Test QueryStatus dataclass creation."""
    status = QueryStatus(
        total_queries=100,
        open_queries=25,
        closed_queries=75,
        overdue_queries=5,
        avg_resolution_days=3.5,
        critical_queries=3
    )
    
    assert status.total_queries == 100
    assert status.open_queries == 25
    assert status.avg_resolution_days == 3.5


def test_safety_event_status_creation():
    """Test SafetyEventStatus dataclass creation."""
    status = SafetyEventStatus(
        total_events=50,
        reconciled_events=40,
        pending_events=10,
        serious_events=5,
        resolved_events=40,
        avg_resolution_days=7.0
    )
    
    assert status.total_events == 50
    assert status.reconciled_events == 40
    assert status.avg_resolution_days == 7.0


def test_monitoring_visit_status_creation():
    """Test MonitoringVisitStatus dataclass creation."""
    status = MonitoringVisitStatus(
        total_sites=20,
        completed_visits=18,
        pending_visits=2,
        overdue_visits=1,
        avg_visit_duration=2.5,
        critical_findings=1
    )
    
    assert status.total_sites == 20
    assert status.completed_visits == 18
    assert status.avg_visit_duration == 2.5


def test_readiness_assessment_creation():
    """Test ReadinessAssessment dataclass creation."""
    assessment = ReadinessAssessment(
        overall_readiness_percentage=85.0,
        projected_lock_date="2024-02-01",
        critical_blockers=["Blocker 1"],
        risk_factors=["Risk 1", "Risk 2"],
        recommendations=["Rec 1", "Rec 2"],
        confidence_level="medium"
    )
    
    assert assessment.overall_readiness_percentage == 85.0
    assert assessment.projected_lock_date == "2024-02-01"
    assert len(assessment.critical_blockers) == 1
    assert len(assessment.risk_factors) == 2
    assert assessment.confidence_level == "medium"