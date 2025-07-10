import pytest
import json
import os
from unittest.mock import Mock, patch

from scripts.medical_coding_agent import (
    CodingSystem,
    TermType,
    UncodedTerm,
    MedicalCode,
    CodingSuggestion,
    load_coding_dictionaries,
    parse_uncoded_terms,
    dictionary_lookup,
    llm_medical_coding,
    combine_coding_suggestions,
    create_coding_suggestion,
    process_medical_coding,
    generate_coding_report,
    export_for_review,
    update_checklist,
    write_progress_log
)


@pytest.fixture
def mock_uncoded_terms():
    """Mock uncoded terms for testing."""
    return [
        UncodedTerm(
            term_id="TERM_001",
            original_text="severe headache",
            term_type=TermType.ADVERSE_EVENT,
            subject_id="SUBJ001",
            visit_name="Visit 1",
            form_name="Adverse Events",
            field_name="ae_term",
            verbatim_term="severe headache",
            context="patient reported severe headache after treatment",
            timestamp="2024-01-01T10:00:00Z"
        ),
        UncodedTerm(
            term_id="TERM_002",
            original_text="aspirin",
            term_type=TermType.MEDICATION,
            subject_id="SUBJ002",
            visit_name="Visit 1",
            form_name="Concomitant Medications",
            field_name="med_name",
            verbatim_term="aspirin",
            context="patient taking aspirin daily",
            timestamp="2024-01-01T10:00:00Z"
        )
    ]


@pytest.fixture
def mock_medical_codes():
    """Mock medical codes for testing."""
    return [
        MedicalCode(
            code="10019211",
            preferred_term="Headache",
            system_organ_class="Nervous system disorders",
            coding_system=CodingSystem.MEDDRA,
            level="PT",
            confidence_score=0.9,
            reasoning="Direct match for headache term"
        ),
        MedicalCode(
            code="10019233",
            preferred_term="Headache severe",
            system_organ_class="Nervous system disorders",
            coding_system=CodingSystem.MEDDRA,
            level="PT",
            confidence_score=0.95,
            reasoning="Exact match for severe headache"
        )
    ]


@pytest.fixture
def mock_dictionaries():
    """Mock coding dictionaries for testing."""
    return {
        CodingSystem.MEDDRA: {
            "terms": [
                {
                    "code": "10019211",
                    "preferred_term": "Headache",
                    "system_organ_class": "Nervous system disorders",
                    "level": "PT",
                    "synonyms": ["head pain", "cephalgia"]
                },
                {
                    "code": "10019233",
                    "preferred_term": "Headache severe",
                    "system_organ_class": "Nervous system disorders",
                    "level": "PT",
                    "synonyms": ["severe head pain", "intense headache"]
                }
            ]
        },
        CodingSystem.WHODD: {
            "terms": [
                {
                    "code": "ASP001",
                    "preferred_term": "Aspirin",
                    "system_organ_class": "Analgesics",
                    "level": "PT",
                    "synonyms": ["acetylsalicylic acid", "ASA"]
                }
            ]
        }
    }


def test_load_coding_dictionaries_success(tmp_path, mock_dictionaries):
    """Test successful loading of coding dictionaries."""
    # Create mock dictionary files
    for coding_system, data in mock_dictionaries.items():
        dict_file = tmp_path / f"{coding_system.value}_dictionary.json"
        dict_file.write_text(json.dumps(data))
    
    dictionaries = load_coding_dictionaries(str(tmp_path))
    
    assert CodingSystem.MEDDRA in dictionaries
    assert CodingSystem.WHODD in dictionaries
    assert len(dictionaries[CodingSystem.MEDDRA]["terms"]) == 2
    assert len(dictionaries[CodingSystem.WHODD]["terms"]) == 1


def test_load_coding_dictionaries_missing_files(tmp_path):
    """Test loading dictionaries when files don't exist."""
    dictionaries = load_coding_dictionaries(str(tmp_path))
    
    # Should create fallback dictionaries
    assert len(dictionaries) == len(CodingSystem)
    for coding_system in CodingSystem:
        assert coding_system in dictionaries
        assert "terms" in dictionaries[coding_system]


def test_parse_uncoded_terms_from_dict():
    """Test parsing uncoded terms from dictionary."""
    terms_data = {
        "uncoded_terms": [
            {
                "term_id": "TERM_001",
                "original_text": "headache",
                "term_type": "adverse_event",
                "subject_id": "SUBJ001",
                "visit_name": "Visit 1",
                "form_name": "AE",
                "field_name": "ae_term",
                "verbatim_term": "headache",
                "context": "mild headache",
                "timestamp": "2024-01-01T10:00:00Z"
            }
        ]
    }
    
    terms = parse_uncoded_terms(terms_data)
    assert len(terms) == 1
    assert terms[0].term_id == "TERM_001"
    assert terms[0].term_type == TermType.ADVERSE_EVENT
    assert terms[0].verbatim_term == "headache"


def test_parse_uncoded_terms_from_file(tmp_path):
    """Test parsing uncoded terms from file."""
    terms_data = {
        "uncoded_terms": [
            {
                "original_text": "nausea",
                "term_type": "adverse_event",
                "subject_id": "SUBJ001"
            }
        ]
    }
    
    terms_file = tmp_path / "terms.json"
    terms_file.write_text(json.dumps(terms_data))
    
    terms = parse_uncoded_terms(str(terms_file))
    assert len(terms) == 1
    assert terms[0].original_text == "nausea"


def test_dictionary_lookup_exact_match(mock_uncoded_terms, mock_dictionaries):
    """Test dictionary lookup with exact match."""
    term = mock_uncoded_terms[0]  # "severe headache"
    
    matches = dictionary_lookup(term, mock_dictionaries)
    
    assert len(matches) > 0
    # Should find exact match for "severe headache"
    exact_matches = [m for m in matches if m.confidence_score == 0.95]
    assert len(exact_matches) > 0
    assert "severe" in exact_matches[0].preferred_term.lower()


def test_dictionary_lookup_partial_match(mock_dictionaries):
    """Test dictionary lookup with partial match."""
    term = UncodedTerm(
        term_id="TEST_001",
        original_text="head pain",
        term_type=TermType.ADVERSE_EVENT,
        subject_id="SUBJ001",
        visit_name="Visit 1",
        form_name="AE",
        field_name="ae_term",
        verbatim_term="head pain",
        context="",
        timestamp="2024-01-01T10:00:00Z"
    )
    
    matches = dictionary_lookup(term, mock_dictionaries)
    
    assert len(matches) > 0
    # Should find partial matches through synonyms
    partial_matches = [m for m in matches if m.confidence_score == 0.75]
    assert len(partial_matches) > 0


def test_dictionary_lookup_no_match(mock_dictionaries):
    """Test dictionary lookup with no matches."""
    term = UncodedTerm(
        term_id="TEST_001",
        original_text="xyz unknown term",
        term_type=TermType.ADVERSE_EVENT,
        subject_id="SUBJ001",
        visit_name="Visit 1",
        form_name="AE",
        field_name="ae_term",
        verbatim_term="xyz unknown term",
        context="",
        timestamp="2024-01-01T10:00:00Z"
    )
    
    matches = dictionary_lookup(term, mock_dictionaries)
    assert len(matches) == 0


def test_llm_medical_coding_success(mocker, mock_uncoded_terms):
    """Test LLM medical coding with successful response."""
    mocker.patch('scripts.medical_coding_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "suggestions": [
            {
                "code": "10019233",
                "preferred_term": "Headache severe",
                "system_organ_class": "Nervous system disorders",
                "level": "PT",
                "confidence_score": 0.95,
                "reasoning": "Exact match for severe headache adverse event"
            }
        ]
    }
    '''
    mocker.patch('scripts.medical_coding_agent.completion', return_value=mock_response)
    
    codes = llm_medical_coding(mock_uncoded_terms[0])
    assert len(codes) == 1
    assert codes[0].code == "10019233"
    assert codes[0].confidence_score == 0.95
    assert "severe" in codes[0].preferred_term.lower()


def test_llm_medical_coding_no_model(mocker, mock_uncoded_terms):
    """Test LLM medical coding when no model is available."""
    mocker.patch('scripts.medical_coding_agent.get_llm_model_name', return_value=None)
    
    codes = llm_medical_coding(mock_uncoded_terms[0])
    assert len(codes) == 0


def test_combine_coding_suggestions(mock_medical_codes):
    """Test combining coding suggestions from different sources."""
    dict_matches = [mock_medical_codes[0]]
    llm_matches = [mock_medical_codes[1]]
    
    combined = combine_coding_suggestions(dict_matches, llm_matches)
    
    assert len(combined) == 2
    # Should be sorted by confidence score (highest first)
    assert combined[0].confidence_score >= combined[1].confidence_score
    
    # Test deduplication
    dict_matches_dup = [mock_medical_codes[0], mock_medical_codes[0]]
    combined_dedup = combine_coding_suggestions(dict_matches_dup, [])
    assert len(combined_dedup) == 1


def test_create_coding_suggestion(mock_uncoded_terms, mock_medical_codes):
    """Test creating coding suggestion from codes."""
    term = mock_uncoded_terms[0]
    codes = mock_medical_codes
    
    suggestion = create_coding_suggestion(term, codes)
    
    assert suggestion.term_id == term.term_id
    assert suggestion.original_text == term.original_text
    assert suggestion.primary_suggestion == codes[0]  # Highest confidence
    assert len(suggestion.alternative_suggestions) <= 4
    assert suggestion.coding_timestamp is not None


def test_create_coding_suggestion_no_codes(mock_uncoded_terms):
    """Test creating coding suggestion when no codes are found."""
    term = mock_uncoded_terms[0]
    
    suggestion = create_coding_suggestion(term, [])
    
    assert suggestion.term_id == term.term_id
    assert suggestion.primary_suggestion.code == "UNCODED"
    assert suggestion.primary_suggestion.confidence_score == 0.0


def test_process_medical_coding(mocker, mock_uncoded_terms, mock_dictionaries):
    """Test processing medical coding for multiple terms."""
    # Mock dictionary lookup
    mocker.patch('scripts.medical_coding_agent.dictionary_lookup', 
                 return_value=[MedicalCode("10019211", "Headache", "Nervous system disorders", 
                                         CodingSystem.MEDDRA, "PT", 0.9, "Dictionary match")])
    
    # Mock LLM coding
    mocker.patch('scripts.medical_coding_agent.llm_medical_coding',
                 return_value=[MedicalCode("10019233", "Headache severe", "Nervous system disorders",
                                         CodingSystem.MEDDRA, "PT", 0.95, "LLM match")])
    
    suggestions = process_medical_coding(mock_uncoded_terms, mock_dictionaries, use_llm=True)
    
    assert len(suggestions) == len(mock_uncoded_terms)
    for suggestion in suggestions:
        assert len(suggestion.suggested_codes) > 0
        assert suggestion.primary_suggestion is not None


def test_generate_coding_report(tmp_path, mock_uncoded_terms, mock_medical_codes):
    """Test generating coding report."""
    suggestions = [
        CodingSuggestion(
            term_id="TERM_001",
            original_text="headache",
            suggested_codes=mock_medical_codes,
            primary_suggestion=mock_medical_codes[0],
            alternative_suggestions=mock_medical_codes[1:],
            coding_timestamp="2024-01-01T10:00:00Z",
            reviewer_notes=""
        )
    ]
    
    report_file = generate_coding_report(suggestions, str(tmp_path))
    
    assert os.path.exists(report_file)
    with open(report_file, "r") as f:
        report_data = json.load(f)
    
    assert report_data["coding_summary"]["total_terms"] == 1
    assert report_data["coding_summary"]["high_confidence_codes"] == 1
    assert len(report_data["coding_suggestions"]) == 1


def test_export_for_review(tmp_path, mock_uncoded_terms, mock_medical_codes):
    """Test exporting coding suggestions for review."""
    suggestions = [
        CodingSuggestion(
            term_id="TERM_001",
            original_text="headache",
            suggested_codes=mock_medical_codes,
            primary_suggestion=mock_medical_codes[0],
            alternative_suggestions=[],
            coding_timestamp="2024-01-01T10:00:00Z",
            reviewer_notes=""
        )
    ]
    
    review_file = export_for_review(suggestions, str(tmp_path))
    
    assert os.path.exists(review_file)
    with open(review_file, "r") as f:
        review_data = json.load(f)
    
    assert len(review_data) == 1
    assert review_data[0]["term_id"] == "TERM_001"
    assert review_data[0]["review_status"] == "pending"
    assert "final_code" in review_data[0]


def test_update_checklist(tmp_path):
    """Test updating checklist file."""
    checklist_data = [
        {"agentId": "3.200", "name": "Medical Coding Agent", "status": 0},
        {"agentId": "3.300", "name": "Other Agent", "status": 50}
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
    log_path = write_progress_log(str(tmp_path), 100, "Medical coding completed")
    
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log_data = json.load(f)
    
    assert log_data["agentId"] == "3.200"
    assert log_data["status"] == 100
    assert log_data["summary"] == "Medical coding completed"
    assert "timestamp" in log_data


def test_uncoded_term_creation():
    """Test UncodedTerm dataclass creation."""
    term = UncodedTerm(
        term_id="TEST_001",
        original_text="test term",
        term_type=TermType.ADVERSE_EVENT,
        subject_id="SUBJ001",
        visit_name="Visit 1",
        form_name="AE",
        field_name="ae_term",
        verbatim_term="test term",
        context="test context",
        timestamp="2024-01-01T10:00:00Z"
    )
    
    assert term.term_id == "TEST_001"
    assert term.term_type == TermType.ADVERSE_EVENT
    assert term.original_text == "test term"


def test_medical_code_creation():
    """Test MedicalCode dataclass creation."""
    code = MedicalCode(
        code="10012345",
        preferred_term="Test Term",
        system_organ_class="Test SOC",
        coding_system=CodingSystem.MEDDRA,
        level="PT",
        confidence_score=0.9,
        reasoning="Test reasoning"
    )
    
    assert code.code == "10012345"
    assert code.coding_system == CodingSystem.MEDDRA
    assert code.confidence_score == 0.9


def test_coding_suggestion_creation():
    """Test CodingSuggestion dataclass creation."""
    primary_code = MedicalCode("10012345", "Test", "SOC", CodingSystem.MEDDRA, "PT", 0.9, "reason")
    
    suggestion = CodingSuggestion(
        term_id="TERM_001",
        original_text="test",
        suggested_codes=[primary_code],
        primary_suggestion=primary_code,
        alternative_suggestions=[],
        coding_timestamp="2024-01-01T10:00:00Z",
        reviewer_notes=""
    )
    
    assert suggestion.term_id == "TERM_001"
    assert suggestion.primary_suggestion == primary_code
    assert len(suggestion.suggested_codes) == 1