import pytest
import json
import os
from unittest.mock import Mock, patch

from scripts.site_monitoring_prioritization_agent import (
    RiskLevel,
    KRICategory,
    KeyRiskIndicator,
    SiteData,
    KRIScore,
    SiteRiskAssessment,
    load_kri_configuration,
    parse_site_data,
    calculate_kri_scores,
    calculate_overall_risk_score,
    determine_risk_level,
    generate_recommendations,
    calculate_next_visit_date,
    assess_site_risks,
    create_monitoring_dashboard,
    update_checklist,
    write_progress_log
)


@pytest.fixture
def mock_kris():
    """Mock Key Risk Indicators for testing."""
    return [
        KeyRiskIndicator(
            kri_id="enrollment_rate",
            name="Enrollment Rate",
            description="Monthly enrollment rate",
            category=KRICategory.ENROLLMENT,
            weight=2.0,
            threshold_low=5.0,
            threshold_medium=10.0,
            threshold_high=15.0,
            unit="subjects/month",
            direction="lower_is_worse"
        ),
        KeyRiskIndicator(
            kri_id="data_query_rate",
            name="Data Query Rate",
            description="Queries per subject",
            category=KRICategory.DATA_QUALITY,
            weight=1.5,
            threshold_low=2.0,
            threshold_medium=5.0,
            threshold_high=8.0,
            unit="queries/subject",
            direction="higher_is_worse"
        ),
        KeyRiskIndicator(
            kri_id="protocol_deviation_rate",
            name="Protocol Deviation Rate",
            description="Protocol deviations per subject",
            category=KRICategory.PROTOCOL_COMPLIANCE,
            weight=1.8,
            threshold_low=0.1,
            threshold_medium=0.2,
            threshold_high=0.3,
            unit="deviations/subject",
            direction="higher_is_worse"
        )
    ]


@pytest.fixture
def mock_sites():
    """Mock site data for testing."""
    return [
        SiteData(
            site_id="SITE_001",
            site_name="Metropolitan Medical Center",
            principal_investigator="Dr. Smith",
            country="USA",
            region="North America",
            enrollment_target=50,
            enrollment_actual=45,
            enrollment_rate=8.0,  # Below threshold - concerning
            data_query_rate=6.0,  # Above medium threshold - concerning
            protocol_deviations=5,
            serious_ae_rate=0.02,
            last_monitoring_visit="2024-01-01T10:00:00Z",
            days_since_last_visit=45,
            data_quality_score=0.85,
            source_data_verification_rate=0.95
        ),
        SiteData(
            site_id="SITE_002",
            site_name="University Hospital",
            principal_investigator="Dr. Johnson",
            country="Canada",
            region="North America",
            enrollment_target=30,
            enrollment_actual=32,
            enrollment_rate=12.0,  # Good enrollment rate
            data_query_rate=3.0,  # Acceptable query rate
            protocol_deviations=1,
            serious_ae_rate=0.01,
            last_monitoring_visit="2024-01-15T10:00:00Z",
            days_since_last_visit=30,
            data_quality_score=0.95,
            source_data_verification_rate=0.98
        ),
        SiteData(
            site_id="SITE_003",
            site_name="City Clinic",
            principal_investigator="Dr. Brown",
            country="UK",
            region="Europe",
            enrollment_target=25,
            enrollment_actual=10,
            enrollment_rate=3.0,  # Very low enrollment - critical
            data_query_rate=12.0,  # Very high query rate - critical
            protocol_deviations=8,
            serious_ae_rate=0.05,
            last_monitoring_visit="2023-12-01T10:00:00Z",
            days_since_last_visit=75,
            data_quality_score=0.65,
            source_data_verification_rate=0.75
        )
    ]


def test_load_kri_configuration_success(tmp_path):
    """Test successful loading of KRI configuration."""
    kri_data = {
        "key_risk_indicators": [
            {
                "kri_id": "enrollment_rate",
                "name": "Enrollment Rate",
                "description": "Monthly enrollment rate",
                "category": "enrollment",
                "weight": 2.0,
                "threshold_low": 5.0,
                "threshold_medium": 10.0,
                "threshold_high": 15.0,
                "unit": "subjects/month",
                "direction": "lower_is_worse"
            }
        ]
    }
    
    kri_file = tmp_path / "kri_config.json"
    kri_file.write_text(json.dumps(kri_data))
    
    kris = load_kri_configuration(str(kri_file))
    assert len(kris) == 1
    assert kris[0].kri_id == "enrollment_rate"
    assert kris[0].category == KRICategory.ENROLLMENT
    assert kris[0].weight == 2.0
    assert kris[0].direction == "lower_is_worse"


def test_load_kri_configuration_file_not_found():
    """Test loading KRI configuration when file doesn't exist."""
    kris = load_kri_configuration("nonexistent.json")
    assert kris == []


def test_parse_site_data_success(tmp_path):
    """Test successful parsing of site data."""
    site_data = {
        "sites": [
            {
                "site_id": "SITE_001",
                "site_name": "Test Site",
                "principal_investigator": "Dr. Test",
                "country": "USA",
                "region": "North America",
                "enrollment_target": 50,
                "enrollment_actual": 45,
                "enrollment_rate": 8.0,
                "data_query_rate": 6.0,
                "protocol_deviations": 5,
                "serious_ae_rate": 0.02,
                "last_monitoring_visit": "2024-01-01T10:00:00Z",
                "data_quality_score": 0.85,
                "source_data_verification_rate": 0.95
            }
        ]
    }
    
    site_file = tmp_path / "site_data.json"
    site_file.write_text(json.dumps(site_data))
    
    sites = parse_site_data(str(site_file))
    assert len(sites) == 1
    assert sites[0].site_id == "SITE_001"
    assert sites[0].enrollment_target == 50
    assert sites[0].days_since_last_visit > 0  # Should calculate days since visit


def test_parse_site_data_file_not_found():
    """Test parsing site data when file doesn't exist."""
    sites = parse_site_data("nonexistent.json")
    assert sites == []


def test_calculate_kri_scores_higher_is_worse(mock_sites, mock_kris):
    """Test KRI score calculation for 'higher is worse' indicators."""
    site = mock_sites[0]  # SITE_001 with high query rate
    data_query_kri = next(kri for kri in mock_kris if kri.kri_id == "data_query_rate")
    
    kri_scores = calculate_kri_scores(site, [data_query_kri])
    
    assert len(kri_scores) == 1
    score = kri_scores[0]
    assert score.kri_id == "data_query_rate"
    assert score.raw_value == 6.0
    # Query rate of 6.0 is above medium threshold (5.0) but below high (8.0)
    assert score.risk_level == RiskLevel.HIGH
    assert score.threshold_exceeded == True


def test_calculate_kri_scores_lower_is_worse(mock_sites, mock_kris):
    """Test KRI score calculation for 'lower is worse' indicators."""
    site = mock_sites[2]  # SITE_003 with very low enrollment rate
    enrollment_kri = next(kri for kri in mock_kris if kri.kri_id == "enrollment_rate")
    
    kri_scores = calculate_kri_scores(site, [enrollment_kri])
    
    assert len(kri_scores) == 1
    score = kri_scores[0]
    assert score.kri_id == "enrollment_rate"
    assert score.raw_value == 3.0
    # Enrollment rate of 3.0 is below low threshold (5.0) - critical risk
    assert score.risk_level == RiskLevel.CRITICAL
    assert score.threshold_exceeded == True


def test_calculate_overall_risk_score():
    """Test overall risk score calculation."""
    kri_scores = [
        KRIScore("kri1", "KRI 1", 5.0, 0.8, RiskLevel.HIGH, 2.0, 1.6, True),
        KRIScore("kri2", "KRI 2", 3.0, 0.4, RiskLevel.MEDIUM, 1.0, 0.4, False),
        KRIScore("kri3", "KRI 3", 2.0, 0.2, RiskLevel.LOW, 1.5, 0.3, False)
    ]
    
    overall_score = calculate_overall_risk_score(kri_scores)
    
    # Weighted average: (1.6 + 0.4 + 0.3) / (2.0 + 1.0 + 1.5) = 2.3 / 4.5 ≈ 0.51
    assert abs(overall_score - 0.51) < 0.01


def test_calculate_overall_risk_score_empty():
    """Test overall risk score calculation with empty list."""
    overall_score = calculate_overall_risk_score([])
    assert overall_score == 0.0


def test_determine_risk_level():
    """Test risk level determination from overall score."""
    assert determine_risk_level(0.9) == RiskLevel.CRITICAL
    assert determine_risk_level(0.7) == RiskLevel.HIGH
    assert determine_risk_level(0.4) == RiskLevel.MEDIUM
    assert determine_risk_level(0.1) == RiskLevel.LOW


def test_generate_recommendations_with_llm(mocker, mock_sites):
    """Test generating recommendations with LLM."""
    mocker.patch('scripts.site_monitoring_prioritization_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "recommendations": [
            "Schedule immediate monitoring visit to address data quality issues",
            "Provide additional training on data entry procedures",
            "Implement enhanced data review processes",
            "Increase frequency of data queries resolution"
        ]
    }
    '''
    mocker.patch('scripts.site_monitoring_prioritization_agent.completion', return_value=mock_response)
    
    site = mock_sites[0]
    kri_scores = [
        KRIScore("data_query_rate", "Data Query Rate", 6.0, 0.8, RiskLevel.HIGH, 1.5, 1.2, True)
    ]
    
    recommendations = generate_recommendations(site, kri_scores, RiskLevel.HIGH)
    
    assert len(recommendations) == 4
    assert "monitoring visit" in recommendations[0].lower()
    assert "training" in recommendations[1].lower()


def test_generate_recommendations_no_llm(mocker, mock_sites):
    """Test generating recommendations without LLM."""
    mocker.patch('scripts.site_monitoring_prioritization_agent.get_llm_model_name', return_value=None)
    
    site = mock_sites[0]
    kri_scores = []
    
    recommendations = generate_recommendations(site, kri_scores, RiskLevel.HIGH)
    
    assert len(recommendations) >= 3
    assert any("priority monitoring visit" in rec.lower() for rec in recommendations)


def test_calculate_next_visit_date():
    """Test next visit date calculation."""
    # Critical risk
    next_date, urgency = calculate_next_visit_date(RiskLevel.CRITICAL, 30)
    assert urgency == "immediate"
    
    # High risk
    next_date, urgency = calculate_next_visit_date(RiskLevel.HIGH, 30)
    assert urgency == "urgent"
    
    # Medium risk
    next_date, urgency = calculate_next_visit_date(RiskLevel.MEDIUM, 30)
    assert urgency == "priority"
    
    # Low risk
    next_date, urgency = calculate_next_visit_date(RiskLevel.LOW, 30)
    assert urgency == "routine"
    
    # Overdue visit (>90 days)
    next_date, urgency = calculate_next_visit_date(RiskLevel.LOW, 95)
    assert urgency == "overdue"


def test_assess_site_risks(mocker, mock_sites, mock_kris):
    """Test comprehensive site risk assessment."""
    # Mock LLM recommendations
    mocker.patch('scripts.site_monitoring_prioritization_agent.generate_recommendations',
                 return_value=["Test recommendation 1", "Test recommendation 2"])
    
    assessments = assess_site_risks(mock_sites, mock_kris)
    
    assert len(assessments) == len(mock_sites)
    
    # Check that sites are ranked by risk (highest first)
    for i in range(len(assessments) - 1):
        assert assessments[i].overall_risk_score >= assessments[i + 1].overall_risk_score
    
    # Check priority ranks are assigned
    for i, assessment in enumerate(assessments):
        assert assessment.priority_rank == i + 1
    
    # Highest risk site should be SITE_003 (low enrollment, high queries)
    highest_risk = assessments[0]
    assert highest_risk.site_id == "SITE_003"
    assert highest_risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


def test_create_monitoring_dashboard(tmp_path, mock_sites, mock_kris):
    """Test creating monitoring dashboard."""
    # Create mock assessments
    assessments = [
        SiteRiskAssessment(
            site_id="SITE_001",
            site_name="Test Site",
            overall_risk_score=0.8,
            risk_level=RiskLevel.HIGH,
            kri_scores=[],
            priority_rank=1,
            recommended_actions=["Action 1", "Action 2"],
            next_visit_recommended="2024-02-01",
            visit_urgency="urgent",
            assessment_timestamp="2024-01-01T10:00:00Z"
        )
    ]
    
    dashboard_file = create_monitoring_dashboard(assessments, mock_kris, str(tmp_path))
    
    assert os.path.exists(dashboard_file)
    with open(dashboard_file, "r") as f:
        dashboard_data = json.load(f)
    
    assert dashboard_data["dashboard_summary"]["total_sites"] == 1
    assert dashboard_data["dashboard_summary"]["high_risk_sites"] == 1
    assert len(dashboard_data["priority_ranking"]) == 1
    assert len(dashboard_data["visit_scheduling"]) == 1
    assert "kri_analysis" in dashboard_data


def test_update_checklist(tmp_path):
    """Test updating checklist file."""
    checklist_data = [
        {"agentId": "3.400", "name": "Site Monitoring Agent", "status": 0},
        {"agentId": "3.500", "name": "Other Agent", "status": 50}
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
    log_path = write_progress_log(str(tmp_path), 100, "Site monitoring prioritization completed")
    
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log_data = json.load(f)
    
    assert log_data["agentId"] == "3.400"
    assert log_data["status"] == 100
    assert log_data["summary"] == "Site monitoring prioritization completed"
    assert "timestamp" in log_data


def test_key_risk_indicator_creation():
    """Test KeyRiskIndicator dataclass creation."""
    kri = KeyRiskIndicator(
        kri_id="test_kri",
        name="Test KRI",
        description="Test description",
        category=KRICategory.DATA_QUALITY,
        weight=1.5,
        threshold_low=1.0,
        threshold_medium=2.0,
        threshold_high=3.0,
        unit="test_unit",
        direction="higher_is_worse"
    )
    
    assert kri.kri_id == "test_kri"
    assert kri.category == KRICategory.DATA_QUALITY
    assert kri.weight == 1.5
    assert kri.direction == "higher_is_worse"


def test_site_data_creation():
    """Test SiteData dataclass creation."""
    site = SiteData(
        site_id="TEST_001",
        site_name="Test Site",
        principal_investigator="Dr. Test",
        country="USA",
        region="North America",
        enrollment_target=50,
        enrollment_actual=45,
        enrollment_rate=8.0,
        data_query_rate=6.0,
        protocol_deviations=5,
        serious_ae_rate=0.02,
        last_monitoring_visit="2024-01-01T10:00:00Z",
        days_since_last_visit=45,
        data_quality_score=0.85,
        source_data_verification_rate=0.95
    )
    
    assert site.site_id == "TEST_001"
    assert site.enrollment_target == 50
    assert site.data_query_rate == 6.0


def test_kri_score_creation():
    """Test KRIScore dataclass creation."""
    score = KRIScore(
        kri_id="test_kri",
        kri_name="Test KRI",
        raw_value=5.0,
        normalized_score=0.8,
        risk_level=RiskLevel.HIGH,
        weight=1.5,
        weighted_score=1.2,
        threshold_exceeded=True
    )
    
    assert score.kri_id == "test_kri"
    assert score.risk_level == RiskLevel.HIGH
    assert score.threshold_exceeded == True


def test_site_risk_assessment_creation():
    """Test SiteRiskAssessment dataclass creation."""
    assessment = SiteRiskAssessment(
        site_id="SITE_001",
        site_name="Test Site",
        overall_risk_score=0.8,
        risk_level=RiskLevel.HIGH,
        kri_scores=[],
        priority_rank=1,
        recommended_actions=["Action 1"],
        next_visit_recommended="2024-02-01",
        visit_urgency="urgent",
        assessment_timestamp="2024-01-01T10:00:00Z"
    )
    
    assert assessment.site_id == "SITE_001"
    assert assessment.risk_level == RiskLevel.HIGH
    assert assessment.priority_rank == 1
    assert assessment.visit_urgency == "urgent"