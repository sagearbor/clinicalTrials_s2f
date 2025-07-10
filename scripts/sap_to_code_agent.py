import os
import json
import logging
import datetime
import re
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
from litellm import completion

from scripts.utils import setup_logging, get_llm_model_name

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

AGENT_ID = "4.200"


class OutputType(Enum):
    TABLE = "table"
    LISTING = "listing"
    FIGURE = "figure"


class AnalysisType(Enum):
    DESCRIPTIVE = "descriptive"
    INFERENTIAL = "inferential"
    SURVIVAL = "survival"
    SAFETY = "safety"
    EFFICACY = "efficacy"
    DEMOGRAPHICS = "demographics"


class CodeLanguage(Enum):
    PYTHON = "python"
    R = "r"


@dataclass
class SAPSection:
    """Represents a section from the Statistical Analysis Plan."""
    section_id: str
    title: str
    content: str
    analysis_type: AnalysisType
    output_type: OutputType
    requirements: List[str]
    datasets_required: List[str]
    variables_required: List[str]


@dataclass
class GeneratedCode:
    """Represents generated statistical code."""
    code_id: str
    section_id: str
    title: str
    language: CodeLanguage
    code_content: str
    analysis_type: AnalysisType
    output_type: OutputType
    dependencies: List[str]
    datasets_used: List[str]
    variables_used: List[str]
    description: str
    validation_notes: str


@dataclass
class TLFSpecification:
    """Represents a Table, Listing, or Figure specification."""
    tlf_id: str
    title: str
    output_type: OutputType
    analysis_population: str
    statistical_methods: List[str]
    grouping_variables: List[str]
    summary_variables: List[str]
    filters: List[str]
    sorting: List[str]
    formatting_requirements: Dict[str, Any]


def parse_sap_document(sap_file: str) -> Dict[str, Any]:
    """Parse SAP document and extract relevant sections."""
    if not os.path.exists(sap_file):
        logger.error(f"SAP document not found: {sap_file}")
        return {}
    
    # For this implementation, we expect a JSON representation of the SAP
    # In a real implementation, this would use PDF/DOCX parsing libraries
    if sap_file.endswith('.json'):
        with open(sap_file, "r") as f:
            return json.load(f)
    else:
        logger.warning("Non-JSON SAP files not fully supported in this implementation")
        return {
            "title": "Statistical Analysis Plan",
            "sections": [],
            "tlf_specifications": [],
            "analysis_populations": [],
            "datasets": [],
            "variables": []
        }


def extract_sap_sections(sap_data: Dict[str, Any]) -> List[SAPSection]:
    """Extract analysis sections from SAP data."""
    sections = []
    
    for section_data in sap_data.get("sections", []):
        section = SAPSection(
            section_id=section_data.get("section_id", ""),
            title=section_data.get("title", ""),
            content=section_data.get("content", ""),
            analysis_type=AnalysisType(section_data.get("analysis_type", "descriptive")),
            output_type=OutputType(section_data.get("output_type", "table")),
            requirements=section_data.get("requirements", []),
            datasets_required=section_data.get("datasets_required", []),
            variables_required=section_data.get("variables_required", [])
        )
        sections.append(section)
    
    logger.info(f"Extracted {len(sections)} SAP sections")
    return sections


def extract_tlf_specifications(sap_data: Dict[str, Any]) -> List[TLFSpecification]:
    """Extract TLF specifications from SAP data."""
    specifications = []
    
    for tlf_data in sap_data.get("tlf_specifications", []):
        spec = TLFSpecification(
            tlf_id=tlf_data.get("tlf_id", ""),
            title=tlf_data.get("title", ""),
            output_type=OutputType(tlf_data.get("output_type", "table")),
            analysis_population=tlf_data.get("analysis_population", ""),
            statistical_methods=tlf_data.get("statistical_methods", []),
            grouping_variables=tlf_data.get("grouping_variables", []),
            summary_variables=tlf_data.get("summary_variables", []),
            filters=tlf_data.get("filters", []),
            sorting=tlf_data.get("sorting", []),
            formatting_requirements=tlf_data.get("formatting_requirements", {})
        )
        specifications.append(spec)
    
    logger.info(f"Extracted {len(specifications)} TLF specifications")
    return specifications


def generate_python_code(section: SAPSection, tlf_spec: TLFSpecification, 
                         dataset_info: Dict[str, Any]) -> GeneratedCode:
    """Generate Python code for statistical analysis."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; generating basic template")
        return create_basic_python_template(section, tlf_spec)
    
    prompt = f"""
    You are a biostatistician and Python expert. Generate executable Python code for the following statistical analysis from a Clinical Trial Statistical Analysis Plan (SAP).
    
    SAP Section:
    - Title: {section.title}
    - Analysis Type: {section.analysis_type.value}
    - Output Type: {section.output_type.value}
    - Content: {section.content}
    - Requirements: {section.requirements}
    
    TLF Specification:
    - TLF ID: {tlf_spec.tlf_id}
    - Title: {tlf_spec.title}
    - Analysis Population: {tlf_spec.analysis_population}
    - Statistical Methods: {tlf_spec.statistical_methods}
    - Grouping Variables: {tlf_spec.grouping_variables}
    - Summary Variables: {tlf_spec.summary_variables}
    - Filters: {tlf_spec.filters}
    
    Dataset Information:
    {json.dumps(dataset_info, indent=2)}
    
    Generate Python code that:
    1. Imports necessary libraries (pandas, numpy, scipy, matplotlib, etc.)
    2. Loads and processes the required datasets
    3. Applies population filters as specified
    4. Performs the required statistical analysis
    5. Generates the specified output (table/listing/figure)
    6. Includes proper error handling and validation
    7. Follows clinical trial statistical programming best practices
    
    Return the code in this JSON format:
    {{
        "code": "# Complete Python code here",
        "dependencies": ["pandas", "numpy", "scipy"],
        "datasets_used": ["dataset1.csv"],
        "variables_used": ["var1", "var2"],
        "description": "Brief description of what the code does",
        "validation_notes": "Notes on validation and quality checks"
    }}
    """
    
    try:
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.choices[0].message.content.strip()
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            result = json.loads(json_str)
            
            generated_code = GeneratedCode(
                code_id=f"{section.section_id}_{tlf_spec.tlf_id}",
                section_id=section.section_id,
                title=f"{section.title} - {tlf_spec.title}",
                language=CodeLanguage.PYTHON,
                code_content=result.get("code", ""),
                analysis_type=section.analysis_type,
                output_type=section.output_type,
                dependencies=result.get("dependencies", []),
                datasets_used=result.get("datasets_used", []),
                variables_used=result.get("variables_used", []),
                description=result.get("description", ""),
                validation_notes=result.get("validation_notes", "")
            )
            
            logger.info(f"Generated Python code for {section.title}")
            return generated_code
        
    except Exception as e:
        logger.error(f"Failed to generate Python code: {e}")
    
    return create_basic_python_template(section, tlf_spec)


def generate_r_code(section: SAPSection, tlf_spec: TLFSpecification, 
                   dataset_info: Dict[str, Any]) -> GeneratedCode:
    """Generate R code for statistical analysis."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; generating basic template")
        return create_basic_r_template(section, tlf_spec)
    
    prompt = f"""
    You are a biostatistician and R expert. Generate executable R code for the following statistical analysis from a Clinical Trial Statistical Analysis Plan (SAP).
    
    SAP Section:
    - Title: {section.title}
    - Analysis Type: {section.analysis_type.value}
    - Output Type: {section.output_type.value}
    - Content: {section.content}
    - Requirements: {section.requirements}
    
    TLF Specification:
    - TLF ID: {tlf_spec.tlf_id}
    - Title: {tlf_spec.title}
    - Analysis Population: {tlf_spec.analysis_population}
    - Statistical Methods: {tlf_spec.statistical_methods}
    - Grouping Variables: {tlf_spec.grouping_variables}
    - Summary Variables: {tlf_spec.summary_variables}
    - Filters: {tlf_spec.filters}
    
    Dataset Information:
    {json.dumps(dataset_info, indent=2)}
    
    Generate R code that:
    1. Loads necessary packages (dplyr, ggplot2, survival, etc.)
    2. Reads and processes the required datasets
    3. Applies population filters as specified
    4. Performs the required statistical analysis
    5. Generates the specified output (table/listing/figure)
    6. Includes proper error handling and validation
    7. Follows clinical trial statistical programming best practices (CDISC standards)
    
    Return the code in this JSON format:
    {{
        "code": "# Complete R code here",
        "dependencies": ["dplyr", "ggplot2", "survival"],
        "datasets_used": ["adsl.xpt", "adae.xpt"],
        "variables_used": ["USUBJID", "AVAL", "TRTA"],
        "description": "Brief description of what the code does",
        "validation_notes": "Notes on validation and quality checks"
    }}
    """
    
    try:
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.choices[0].message.content.strip()
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            result = json.loads(json_str)
            
            generated_code = GeneratedCode(
                code_id=f"{section.section_id}_{tlf_spec.tlf_id}",
                section_id=section.section_id,
                title=f"{section.title} - {tlf_spec.title}",
                language=CodeLanguage.R,
                code_content=result.get("code", ""),
                analysis_type=section.analysis_type,
                output_type=section.output_type,
                dependencies=result.get("dependencies", []),
                datasets_used=result.get("datasets_used", []),
                variables_used=result.get("variables_used", []),
                description=result.get("description", ""),
                validation_notes=result.get("validation_notes", "")
            )
            
            logger.info(f"Generated R code for {section.title}")
            return generated_code
        
    except Exception as e:
        logger.error(f"Failed to generate R code: {e}")
    
    return create_basic_r_template(section, tlf_spec)


def create_basic_python_template(section: SAPSection, tlf_spec: TLFSpecification) -> GeneratedCode:
    """Create a basic Python code template when LLM is not available."""
    template_code = f'''
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# {section.title} - {tlf_spec.title}
# Analysis Type: {section.analysis_type.value}
# Output Type: {section.output_type.value}

def main():
    """
    Main function to execute {section.title} analysis
    """
    try:
        # Load datasets
        # data = pd.read_csv('your_dataset.csv')
        
        # Apply filters for analysis population: {tlf_spec.analysis_population}
        # filtered_data = data[data['population_flag'] == 1]
        
        # Perform statistical analysis
        # Add your analysis code here based on: {tlf_spec.statistical_methods}
        
        # Generate output
        print(f"Analysis: {section.title}")
        print(f"Output: {tlf_spec.title}")
        
        # Return results
        return {{"status": "completed", "output_file": "output.csv"}}
        
    except Exception as e:
        print(f"Error in analysis: {{e}}")
        return {{"status": "error", "message": str(e)}}

if __name__ == "__main__":
    result = main()
    print(result)
'''
    
    return GeneratedCode(
        code_id=f"{section.section_id}_{tlf_spec.tlf_id}",
        section_id=section.section_id,
        title=f"{section.title} - {tlf_spec.title}",
        language=CodeLanguage.PYTHON,
        code_content=template_code,
        analysis_type=section.analysis_type,
        output_type=section.output_type,
        dependencies=["pandas", "numpy", "matplotlib", "scipy"],
        datasets_used=section.datasets_required,
        variables_used=section.variables_required,
        description=f"Template code for {section.title}",
        validation_notes="Template code - requires customization for specific analysis"
    )


def create_basic_r_template(section: SAPSection, tlf_spec: TLFSpecification) -> GeneratedCode:
    """Create a basic R code template when LLM is not available."""
    template_code = f'''
# {section.title} - {tlf_spec.title}
# Analysis Type: {section.analysis_type.value}
# Output Type: {section.output_type.value}

library(dplyr)
library(ggplot2)
library(haven)

main <- function() {{
  tryCatch({{
    # Load datasets
    # data <- read_sas("your_dataset.sas7bdat")
    
    # Apply filters for analysis population: {tlf_spec.analysis_population}
    # filtered_data <- data %>% filter(population_flag == 1)
    
    # Perform statistical analysis
    # Add your analysis code here based on: {tlf_spec.statistical_methods}
    
    # Generate output
    cat("Analysis:", "{section.title}\\n")
    cat("Output:", "{tlf_spec.title}\\n")
    
    # Return results
    list(status = "completed", output_file = "output.csv")
    
  }}, error = function(e) {{
    cat("Error in analysis:", e$message, "\\n")
    list(status = "error", message = e$message)
  }})
}}

# Execute main function
result <- main()
print(result)
'''
    
    return GeneratedCode(
        code_id=f"{section.section_id}_{tlf_spec.tlf_id}",
        section_id=section.section_id,
        title=f"{section.title} - {tlf_spec.title}",
        language=CodeLanguage.R,
        code_content=template_code,
        analysis_type=section.analysis_type,
        output_type=section.output_type,
        dependencies=["dplyr", "ggplot2", "haven"],
        datasets_used=section.datasets_required,
        variables_used=section.variables_required,
        description=f"Template code for {section.title}",
        validation_notes="Template code - requires customization for specific analysis"
    )


def process_sap_to_code(sections: List[SAPSection], tlf_specs: List[TLFSpecification], 
                       dataset_info: Dict[str, Any], languages: List[CodeLanguage]) -> List[GeneratedCode]:
    """Process SAP sections and generate code in specified languages."""
    generated_codes = []
    
    for section in sections:
        # Find matching TLF specification
        matching_tlfs = [tlf for tlf in tlf_specs if tlf.output_type == section.output_type]
        
        if not matching_tlfs:
            # Create a basic TLF spec if none found
            basic_tlf = TLFSpecification(
                tlf_id=f"TLF_{section.section_id}",
                title=section.title,
                output_type=section.output_type,
                analysis_population="All Subjects",
                statistical_methods=["Descriptive Statistics"],
                grouping_variables=[],
                summary_variables=[],
                filters=[],
                sorting=[],
                formatting_requirements={}
            )
            matching_tlfs = [basic_tlf]
        
        for tlf_spec in matching_tlfs:
            for language in languages:
                if language == CodeLanguage.PYTHON:
                    code = generate_python_code(section, tlf_spec, dataset_info)
                elif language == CodeLanguage.R:
                    code = generate_r_code(section, tlf_spec, dataset_info)
                else:
                    continue
                
                generated_codes.append(code)
    
    logger.info(f"Generated {len(generated_codes)} code scripts")
    return generated_codes


def save_generated_code(generated_codes: List[GeneratedCode], output_dir: str) -> List[str]:
    """Save generated code to files."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved_files = []
    
    for code in generated_codes:
        # Determine file extension
        extension = ".py" if code.language == CodeLanguage.PYTHON else ".R"
        
        # Create filename
        safe_title = re.sub(r'[^a-zA-Z0-9_]', '_', code.title)
        filename = f"{code.code_id}_{safe_title}{extension}"
        filepath = os.path.join(output_dir, filename)
        
        # Add header comment
        header = f"""
# Generated Code: {code.title}
# Code ID: {code.code_id}
# Section ID: {code.section_id}
# Language: {code.language.value}
# Analysis Type: {code.analysis_type.value}
# Output Type: {code.output_type.value}
# Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
#
# Description: {code.description}
# Validation Notes: {code.validation_notes}
#
# Dependencies: {', '.join(code.dependencies)}
# Datasets Used: {', '.join(code.datasets_used)}
# Variables Used: {', '.join(code.variables_used)}
#

"""
        
        # Write code to file
        with open(filepath, "w") as f:
            f.write(header + code.code_content)
        
        saved_files.append(filepath)
        logger.info(f"Saved generated code to {filepath}")
    
    return saved_files


def create_code_summary_report(generated_codes: List[GeneratedCode], output_dir: str) -> str:
    """Create a summary report of all generated code."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    report_data = {
        "summary": {
            "total_scripts": len(generated_codes),
            "python_scripts": len([c for c in generated_codes if c.language == CodeLanguage.PYTHON]),
            "r_scripts": len([c for c in generated_codes if c.language == CodeLanguage.R]),
            "analysis_types": list(set(c.analysis_type.value for c in generated_codes)),
            "output_types": list(set(c.output_type.value for c in generated_codes)),
            "generation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        },
        "generated_codes": [
            {
                "code_id": code.code_id,
                "title": code.title,
                "language": code.language.value,
                "analysis_type": code.analysis_type.value,
                "output_type": code.output_type.value,
                "dependencies": code.dependencies,
                "datasets_used": code.datasets_used,
                "variables_used": code.variables_used,
                "description": code.description,
                "validation_notes": code.validation_notes
            } for code in generated_codes
        ],
        "execution_instructions": {
            "python": "Execute Python scripts using: python script_name.py",
            "r": "Execute R scripts using: Rscript script_name.R",
            "notes": "Ensure all dependencies are installed and datasets are available before execution"
        }
    }
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    report_file = os.path.join(output_dir, f"sap_code_generation_report_{timestamp}.json")
    
    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=2)
    
    logger.info(f"Code generation report saved to {report_file}")
    return report_file


def update_checklist(checklist_path: str, status_val: int) -> None:
    """Update the checklist.yml file for this agent."""
    import yaml
    
    with open(checklist_path, "r") as f:
        tasks = yaml.safe_load(f)

    for task in tasks:
        if task.get("agentId") == AGENT_ID:
            task["status"] = status_val
            break

    with open(checklist_path, "w") as f:
        yaml.safe_dump(tasks, f)


def write_progress_log(log_dir: str, status_val: int, summary: str) -> str:
    """Write a progress log JSON file."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"{AGENT_ID}-{status_val}-{timestamp}.json"
    log_path = os.path.join(log_dir, filename)

    data = {
        "agentId": AGENT_ID,
        "status": status_val,
        "summary": summary,
        "timestamp": timestamp,
    }
    with open(log_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Progress log written to {log_path}")
    return log_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Statistical Analysis Plan to Code Agent")
    parser.add_argument("sap_file", help="Path to SAP document (JSON format)")
    parser.add_argument("--dataset_info", help="Path to dataset information file")
    parser.add_argument("--languages", nargs="+", choices=["python", "r"], default=["python"], 
                       help="Programming languages to generate code for")
    parser.add_argument("--output_dir", default="output", help="Directory for generated code")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Parse SAP document
    sap_data = parse_sap_document(args.sap_file)
    if not sap_data:
        logger.error("Failed to parse SAP document")
        return

    # Extract sections and TLF specifications
    sections = extract_sap_sections(sap_data)
    tlf_specs = extract_tlf_specifications(sap_data)
    
    if not sections:
        logger.error("No SAP sections found")
        return

    # Load dataset information
    dataset_info = {}
    if args.dataset_info and os.path.exists(args.dataset_info):
        with open(args.dataset_info, "r") as f:
            dataset_info = json.load(f)
    else:
        dataset_info = sap_data.get("datasets", {})

    # Convert language arguments to enum
    languages = [CodeLanguage(lang.lower()) for lang in args.languages]

    # Generate code
    generated_codes = process_sap_to_code(sections, tlf_specs, dataset_info, languages)

    # Save generated code
    saved_files = save_generated_code(generated_codes, args.output_dir)

    # Create summary report
    report_file = create_code_summary_report(generated_codes, args.output_dir)

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    
    python_scripts = len([c for c in generated_codes if c.language == CodeLanguage.PYTHON])
    r_scripts = len([c for c in generated_codes if c.language == CodeLanguage.R])
    summary = f"SAP to code generation completed: {len(generated_codes)} scripts generated ({python_scripts} Python, {r_scripts} R)"
    
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        summary
    )

    logger.info(f"SAP to code generation complete: {len(generated_codes)} scripts generated")
    logger.info(f"Generated files saved to: {args.output_dir}")


if __name__ == "__main__":
    main()