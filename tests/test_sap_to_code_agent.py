import pytest
import json
import os
from unittest.mock import Mock, patch

from scripts.sap_to_code_agent import (
    OutputType,
    AnalysisType,
    CodeLanguage,
    SAPSection,
    GeneratedCode,
    TLFSpecification,
    parse_sap_document,
    extract_sap_sections,
    extract_tlf_specifications,
    generate_python_code,
    generate_r_code,
    create_basic_python_template,
    create_basic_r_template,
    process_sap_to_code,
    save_generated_code,
    create_code_summary_report,
    update_checklist,
    write_progress_log
)


@pytest.fixture
def mock_sap_data():
    """Mock SAP data for testing."""
    return {
        "title": "Statistical Analysis Plan",
        "sections": [
            {
                "section_id": "DEMO_01",
                "title": "Demographics Table",
                "content": "Generate demographics summary table by treatment group",
                "analysis_type": "descriptive",
                "output_type": "table",
                "requirements": ["Summary statistics by treatment group"],
                "datasets_required": ["adsl.xpt"],
                "variables_required": ["AGE", "SEX", "RACE", "TRT01A"]
            },
            {
                "section_id": "EFF_01",
                "title": "Primary Efficacy Analysis",
                "content": "ANCOVA analysis of primary endpoint",
                "analysis_type": "inferential",
                "output_type": "table",
                "requirements": ["ANCOVA with baseline as covariate"],
                "datasets_required": ["adeff.xpt"],
                "variables_required": ["AVAL", "BASE", "TRT01A", "VISIT"]
            }
        ],
        "tlf_specifications": [
            {
                "tlf_id": "T_14_01",
                "title": "Demographics and Baseline Characteristics",
                "output_type": "table",
                "analysis_population": "Safety Population",
                "statistical_methods": ["Descriptive Statistics"],
                "grouping_variables": ["TRT01A"],
                "summary_variables": ["AGE", "SEX", "RACE"],
                "filters": ["SAFFL='Y'"],
                "sorting": ["TRT01A", "USUBJID"],
                "formatting_requirements": {"decimals": 1}
            }
        ],
        "datasets": {
            "adsl": {"path": "adsl.xpt", "type": "subject_level"},
            "adeff": {"path": "adeff.xpt", "type": "efficacy"}
        }
    }


@pytest.fixture
def mock_sap_sections():
    """Mock SAP sections for testing."""
    return [
        SAPSection(
            section_id="DEMO_01",
            title="Demographics Table",
            content="Generate demographics summary table",
            analysis_type=AnalysisType.DESCRIPTIVE,
            output_type=OutputType.TABLE,
            requirements=["Summary statistics"],
            datasets_required=["adsl.xpt"],
            variables_required=["AGE", "SEX", "RACE"]
        ),
        SAPSection(
            section_id="EFF_01",
            title="Primary Efficacy Analysis",
            content="ANCOVA analysis",
            analysis_type=AnalysisType.INFERENTIAL,
            output_type=OutputType.TABLE,
            requirements=["ANCOVA with baseline"],
            datasets_required=["adeff.xpt"],
            variables_required=["AVAL", "BASE", "TRT01A"]
        )
    ]


@pytest.fixture
def mock_tlf_specs():
    """Mock TLF specifications for testing."""
    return [
        TLFSpecification(
            tlf_id="T_14_01",
            title="Demographics Table",
            output_type=OutputType.TABLE,
            analysis_population="Safety Population",
            statistical_methods=["Descriptive Statistics"],
            grouping_variables=["TRT01A"],
            summary_variables=["AGE", "SEX", "RACE"],
            filters=["SAFFL='Y'"],
            sorting=["TRT01A"],
            formatting_requirements={"decimals": 1}
        )
    ]


@pytest.fixture
def mock_generated_codes():
    """Mock generated codes for testing."""
    return [
        GeneratedCode(
            code_id="DEMO_01_T_14_01",
            section_id="DEMO_01",
            title="Demographics Table",
            language=CodeLanguage.PYTHON,
            code_content="import pandas as pd\n# Demographics analysis code",
            analysis_type=AnalysisType.DESCRIPTIVE,
            output_type=OutputType.TABLE,
            dependencies=["pandas", "numpy"],
            datasets_used=["adsl.xpt"],
            variables_used=["AGE", "SEX", "RACE"],
            description="Demographics summary table",
            validation_notes="Validate output format"
        )
    ]


def test_parse_sap_document_json(tmp_path, mock_sap_data):
    """Test parsing SAP document from JSON file."""
    sap_file = tmp_path / "sap.json"
    sap_file.write_text(json.dumps(mock_sap_data))
    
    result = parse_sap_document(str(sap_file))
    assert result["title"] == "Statistical Analysis Plan"
    assert len(result["sections"]) == 2
    assert len(result["tlf_specifications"]) == 1


def test_parse_sap_document_file_not_found():
    """Test parsing SAP document when file doesn't exist."""
    result = parse_sap_document("nonexistent.json")
    assert result == {}


def test_parse_sap_document_non_json(tmp_path):
    """Test parsing non-JSON SAP document."""
    sap_file = tmp_path / "sap.pdf"
    sap_file.write_text("This is a PDF file")
    
    result = parse_sap_document(str(sap_file))
    assert result["title"] == "Statistical Analysis Plan"
    assert "sections" in result


def test_extract_sap_sections(mock_sap_data):
    """Test extracting SAP sections from data."""
    sections = extract_sap_sections(mock_sap_data)
    
    assert len(sections) == 2
    assert sections[0].section_id == "DEMO_01"
    assert sections[0].analysis_type == AnalysisType.DESCRIPTIVE
    assert sections[0].output_type == OutputType.TABLE
    assert "adsl.xpt" in sections[0].datasets_required


def test_extract_tlf_specifications(mock_sap_data):
    """Test extracting TLF specifications from data."""
    specs = extract_tlf_specifications(mock_sap_data)
    
    assert len(specs) == 1
    assert specs[0].tlf_id == "T_14_01"
    assert specs[0].output_type == OutputType.TABLE
    assert "TRT01A" in specs[0].grouping_variables


def test_generate_python_code_success(mocker, mock_sap_sections, mock_tlf_specs):
    """Test successful Python code generation with LLM."""
    mocker.patch('scripts.sap_to_code_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "code": "import pandas as pd\\nimport numpy as np\\n\\n# Demographics analysis\\ndata = pd.read_sas('adsl.xpt')\\nsummary = data.groupby('TRT01A').describe()\\nprint(summary)",
        "dependencies": ["pandas", "numpy"],
        "datasets_used": ["adsl.xpt"],
        "variables_used": ["AGE", "SEX", "RACE", "TRT01A"],
        "description": "Demographics summary table by treatment group",
        "validation_notes": "Verify population filters and summary statistics"
    }
    '''
    mocker.patch('scripts.sap_to_code_agent.completion', return_value=mock_response)
    
    section = mock_sap_sections[0]
    tlf_spec = mock_tlf_specs[0]
    dataset_info = {"adsl": {"path": "adsl.xpt"}}
    
    result = generate_python_code(section, tlf_spec, dataset_info)
    
    assert result.language == CodeLanguage.PYTHON
    assert "import pandas as pd" in result.code_content
    assert "pandas" in result.dependencies
    assert result.analysis_type == AnalysisType.DESCRIPTIVE


def test_generate_python_code_no_llm(mocker, mock_sap_sections, mock_tlf_specs):
    """Test Python code generation without LLM."""
    mocker.patch('scripts.sap_to_code_agent.get_llm_model_name', return_value=None)
    
    section = mock_sap_sections[0]
    tlf_spec = mock_tlf_specs[0]
    dataset_info = {}
    
    result = generate_python_code(section, tlf_spec, dataset_info)
    
    assert result.language == CodeLanguage.PYTHON
    assert "import pandas as pd" in result.code_content
    assert "Template code" in result.validation_notes


def test_generate_r_code_success(mocker, mock_sap_sections, mock_tlf_specs):
    """Test successful R code generation with LLM."""
    mocker.patch('scripts.sap_to_code_agent.get_llm_model_name', return_value='gpt-4')
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "code": "library(dplyr)\\nlibrary(haven)\\n\\n# Demographics analysis\\ndata <- read_sas('adsl.xpt')\\nsummary <- data %>% group_by(TRT01A) %>% summarise_all(mean, na.rm=TRUE)\\nprint(summary)",
        "dependencies": ["dplyr", "haven"],
        "datasets_used": ["adsl.xpt"],
        "variables_used": ["AGE", "SEX", "RACE", "TRT01A"],
        "description": "Demographics summary table using R",
        "validation_notes": "Check for missing values and outliers"
    }
    '''
    mocker.patch('scripts.sap_to_code_agent.completion', return_value=mock_response)
    
    section = mock_sap_sections[0]
    tlf_spec = mock_tlf_specs[0]
    dataset_info = {"adsl": {"path": "adsl.xpt"}}
    
    result = generate_r_code(section, tlf_spec, dataset_info)
    
    assert result.language == CodeLanguage.R
    assert "library(dplyr)" in result.code_content
    assert "dplyr" in result.dependencies


def test_generate_r_code_no_llm(mocker, mock_sap_sections, mock_tlf_specs):
    """Test R code generation without LLM."""
    mocker.patch('scripts.sap_to_code_agent.get_llm_model_name', return_value=None)
    
    section = mock_sap_sections[0]
    tlf_spec = mock_tlf_specs[0]
    dataset_info = {}
    
    result = generate_r_code(section, tlf_spec, dataset_info)
    
    assert result.language == CodeLanguage.R
    assert "library(dplyr)" in result.code_content
    assert "Template code" in result.validation_notes


def test_create_basic_python_template(mock_sap_sections, mock_tlf_specs):
    """Test creating basic Python template."""
    section = mock_sap_sections[0]
    tlf_spec = mock_tlf_specs[0]
    
    result = create_basic_python_template(section, tlf_spec)
    
    assert result.language == CodeLanguage.PYTHON
    assert "import pandas as pd" in result.code_content
    assert "def main():" in result.code_content
    assert result.section_id == section.section_id


def test_create_basic_r_template(mock_sap_sections, mock_tlf_specs):
    """Test creating basic R template."""
    section = mock_sap_sections[0]
    tlf_spec = mock_tlf_specs[0]
    
    result = create_basic_r_template(section, tlf_spec)
    
    assert result.language == CodeLanguage.R
    assert "library(dplyr)" in result.code_content
    assert "main <- function()" in result.code_content
    assert result.section_id == section.section_id


def test_process_sap_to_code(mocker, mock_sap_sections, mock_tlf_specs):
    """Test processing SAP to code generation."""
    # Mock code generation functions
    mocker.patch('scripts.sap_to_code_agent.generate_python_code', 
                 return_value=GeneratedCode("test_py", "DEMO_01", "Test", CodeLanguage.PYTHON, 
                                          "print('test')", AnalysisType.DESCRIPTIVE, OutputType.TABLE,
                                          [], [], [], "", ""))
    mocker.patch('scripts.sap_to_code_agent.generate_r_code',
                 return_value=GeneratedCode("test_r", "DEMO_01", "Test", CodeLanguage.R,
                                          "print('test')", AnalysisType.DESCRIPTIVE, OutputType.TABLE,
                                          [], [], [], "", ""))
    
    dataset_info = {"adsl": {"path": "adsl.xpt"}}
    languages = [CodeLanguage.PYTHON, CodeLanguage.R]
    
    result = process_sap_to_code(mock_sap_sections, mock_tlf_specs, dataset_info, languages)
    
    # Should generate code for each section in each language
    assert len(result) >= 2  # At least one for each language
    python_codes = [c for c in result if c.language == CodeLanguage.PYTHON]
    r_codes = [c for c in result if c.language == CodeLanguage.R]
    assert len(python_codes) > 0
    assert len(r_codes) > 0


def test_process_sap_to_code_no_matching_tlf(mock_sap_sections):
    """Test processing SAP to code when no matching TLF specs."""
    dataset_info = {}
    languages = [CodeLanguage.PYTHON]
    
    # Empty TLF specs list
    result = process_sap_to_code(mock_sap_sections, [], dataset_info, languages)
    
    # Should still generate code with basic TLF specs
    assert len(result) > 0


def test_save_generated_code(tmp_path, mock_generated_codes):
    """Test saving generated code to files."""
    saved_files = save_generated_code(mock_generated_codes, str(tmp_path))
    
    assert len(saved_files) == 1
    assert saved_files[0].endswith('.py')
    assert os.path.exists(saved_files[0])
    
    # Check file content
    with open(saved_files[0], 'r') as f:
        content = f.read()
    
    assert "Generated Code:" in content
    assert "import pandas as pd" in content


def test_save_generated_code_r_language(tmp_path):
    """Test saving R code to files."""
    r_code = GeneratedCode(
        code_id="TEST_R",
        section_id="TEST",
        title="Test R Code",
        language=CodeLanguage.R,
        code_content="library(dplyr)\nprint('test')",
        analysis_type=AnalysisType.DESCRIPTIVE,
        output_type=OutputType.TABLE,
        dependencies=["dplyr"],
        datasets_used=["test.xpt"],
        variables_used=["VAR1"],
        description="Test R code",
        validation_notes="Test validation"
    )
    
    saved_files = save_generated_code([r_code], str(tmp_path))
    
    assert len(saved_files) == 1
    assert saved_files[0].endswith('.R')
    assert os.path.exists(saved_files[0])


def test_create_code_summary_report(tmp_path, mock_generated_codes):
    """Test creating code summary report."""
    report_file = create_code_summary_report(mock_generated_codes, str(tmp_path))
    
    assert os.path.exists(report_file)
    with open(report_file, 'r') as f:
        report_data = json.load(f)
    
    assert report_data["summary"]["total_scripts"] == 1
    assert report_data["summary"]["python_scripts"] == 1
    assert report_data["summary"]["r_scripts"] == 0
    assert len(report_data["generated_codes"]) == 1
    assert "execution_instructions" in report_data


def test_update_checklist(tmp_path):
    """Test updating checklist file."""
    checklist_data = [
        {"agentId": "4.200", "name": "SAP to Code Agent", "status": 0},
        {"agentId": "4.300", "name": "Other Agent", "status": 50}
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
    log_path = write_progress_log(str(tmp_path), 100, "SAP to code generation completed")
    
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log_data = json.load(f)
    
    assert log_data["agentId"] == "4.200"
    assert log_data["status"] == 100
    assert log_data["summary"] == "SAP to code generation completed"
    assert "timestamp" in log_data


def test_sap_section_creation():
    """Test SAPSection dataclass creation."""
    section = SAPSection(
        section_id="TEST_01",
        title="Test Section",
        content="Test content",
        analysis_type=AnalysisType.DESCRIPTIVE,
        output_type=OutputType.TABLE,
        requirements=["Test requirement"],
        datasets_required=["test.xpt"],
        variables_required=["VAR1", "VAR2"]
    )
    
    assert section.section_id == "TEST_01"
    assert section.analysis_type == AnalysisType.DESCRIPTIVE
    assert section.output_type == OutputType.TABLE
    assert len(section.variables_required) == 2


def test_generated_code_creation():
    """Test GeneratedCode dataclass creation."""
    code = GeneratedCode(
        code_id="TEST_CODE",
        section_id="TEST_01",
        title="Test Code",
        language=CodeLanguage.PYTHON,
        code_content="print('test')",
        analysis_type=AnalysisType.DESCRIPTIVE,
        output_type=OutputType.TABLE,
        dependencies=["pandas"],
        datasets_used=["test.csv"],
        variables_used=["VAR1"],
        description="Test description",
        validation_notes="Test validation"
    )
    
    assert code.code_id == "TEST_CODE"
    assert code.language == CodeLanguage.PYTHON
    assert code.analysis_type == AnalysisType.DESCRIPTIVE


def test_tlf_specification_creation():
    """Test TLFSpecification dataclass creation."""
    spec = TLFSpecification(
        tlf_id="T_01_01",
        title="Test Table",
        output_type=OutputType.TABLE,
        analysis_population="All Subjects",
        statistical_methods=["Descriptive Statistics"],
        grouping_variables=["TRT01A"],
        summary_variables=["AGE", "SEX"],
        filters=["SAFFL='Y'"],
        sorting=["TRT01A"],
        formatting_requirements={"decimals": 2}
    )
    
    assert spec.tlf_id == "T_01_01"
    assert spec.output_type == OutputType.TABLE
    assert len(spec.summary_variables) == 2
    assert spec.formatting_requirements["decimals"] == 2