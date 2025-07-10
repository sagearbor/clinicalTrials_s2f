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

AGENT_ID = "4.300"


class CSRSection(Enum):
    TITLE_PAGE = "title_page"
    SYNOPSIS = "synopsis"
    TABLE_OF_CONTENTS = "table_of_contents"
    LIST_OF_ABBREVIATIONS = "list_of_abbreviations"
    ETHICS = "ethics"
    INVESTIGATORS_SITES = "investigators_sites"
    INTRODUCTION = "introduction"
    STUDY_OBJECTIVES = "study_objectives"
    INVESTIGATIONAL_PLAN = "investigational_plan"
    STUDY_SUBJECTS = "study_subjects"
    EFFICACY_EVALUATION = "efficacy_evaluation"
    SAFETY_EVALUATION = "safety_evaluation"
    DISCUSSION_CONCLUSIONS = "discussion_conclusions"
    TABLES_FIGURES_LISTINGS = "tables_figures_listings"
    APPENDICES = "appendices"


class TLFType(Enum):
    TABLE = "table"
    FIGURE = "figure"
    LISTING = "listing"


@dataclass
class TLFItem:
    """Represents a Table, Listing, or Figure item."""
    tlf_id: str
    title: str
    tlf_type: TLFType
    file_path: str
    section_reference: CSRSection
    description: str
    page_reference: Optional[str] = None


@dataclass
class BoilerplateText:
    """Represents boilerplate text for CSR sections."""
    section: CSRSection
    content: str
    placeholders: List[str]
    is_template: bool = True


@dataclass
class ProtocolInfo:
    """Represents protocol information for CSR."""
    protocol_number: str
    protocol_title: str
    sponsor: str
    indication: str
    study_phase: str
    study_design: str
    primary_objectives: List[str]
    secondary_objectives: List[str]
    primary_endpoints: List[str]
    secondary_endpoints: List[str]
    study_population: str
    sample_size: int
    study_duration: str


@dataclass
class CSRDocument:
    """Represents the complete CSR document structure."""
    protocol_info: ProtocolInfo
    sections: Dict[CSRSection, str]
    tlf_items: List[TLFItem]
    metadata: Dict[str, Any]
    generation_timestamp: str


def load_protocol_info(protocol_file: str) -> ProtocolInfo:
    """Load protocol information from file."""
    if not os.path.exists(protocol_file):
        logger.error(f"Protocol file not found: {protocol_file}")
        return create_default_protocol_info()
    
    with open(protocol_file, "r") as f:
        protocol_data = json.load(f)
    
    return ProtocolInfo(
        protocol_number=protocol_data.get("protocol_number", "PROTO-001"),
        protocol_title=protocol_data.get("protocol_title", "Clinical Trial Protocol"),
        sponsor=protocol_data.get("sponsor", "Sponsor Name"),
        indication=protocol_data.get("indication", "Medical Condition"),
        study_phase=protocol_data.get("study_phase", "Phase II"),
        study_design=protocol_data.get("study_design", "Randomized, Double-blind, Placebo-controlled"),
        primary_objectives=protocol_data.get("primary_objectives", []),
        secondary_objectives=protocol_data.get("secondary_objectives", []),
        primary_endpoints=protocol_data.get("primary_endpoints", []),
        secondary_endpoints=protocol_data.get("secondary_endpoints", []),
        study_population=protocol_data.get("study_population", "Adult patients"),
        sample_size=protocol_data.get("sample_size", 100),
        study_duration=protocol_data.get("study_duration", "12 months")
    )


def create_default_protocol_info() -> ProtocolInfo:
    """Create default protocol information when file is not available."""
    return ProtocolInfo(
        protocol_number="PROTO-001",
        protocol_title="Clinical Trial Protocol",
        sponsor="Sponsor Name",
        indication="Medical Condition",
        study_phase="Phase II",
        study_design="Randomized, Double-blind, Placebo-controlled",
        primary_objectives=["To evaluate efficacy"],
        secondary_objectives=["To evaluate safety"],
        primary_endpoints=["Primary endpoint"],
        secondary_endpoints=["Secondary endpoint"],
        study_population="Adult patients",
        sample_size=100,
        study_duration="12 months"
    )


def load_tlf_items(tlf_directory: str) -> List[TLFItem]:
    """Load TLF items from directory."""
    tlf_items = []
    
    if not os.path.exists(tlf_directory):
        logger.warning(f"TLF directory not found: {tlf_directory}")
        return tlf_items
    
    # Look for TLF catalog file first
    catalog_file = os.path.join(tlf_directory, "tlf_catalog.json")
    if os.path.exists(catalog_file):
        with open(catalog_file, "r") as f:
            catalog_data = json.load(f)
        
        for item_data in catalog_data.get("tlf_items", []):
            tlf_item = TLFItem(
                tlf_id=item_data["tlf_id"],
                title=item_data["title"],
                tlf_type=TLFType(item_data["tlf_type"]),
                file_path=os.path.join(tlf_directory, item_data["file_path"]),
                section_reference=CSRSection(item_data.get("section_reference", "tables_figures_listings")),
                description=item_data.get("description", ""),
                page_reference=item_data.get("page_reference")
            )
            tlf_items.append(tlf_item)
    else:
        # Scan directory for TLF files
        for file_path in Path(tlf_directory).rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.pdf', '.html', '.csv']:
                file_name = file_path.stem
                
                # Determine TLF type from filename
                if file_name.lower().startswith('t_') or 'table' in file_name.lower():
                    tlf_type = TLFType.TABLE
                elif file_name.lower().startswith('f_') or 'figure' in file_name.lower():
                    tlf_type = TLFType.FIGURE
                elif file_name.lower().startswith('l_') or 'listing' in file_name.lower():
                    tlf_type = TLFType.LISTING
                else:
                    tlf_type = TLFType.TABLE  # Default
                
                tlf_item = TLFItem(
                    tlf_id=file_name,
                    title=file_name.replace('_', ' ').title(),
                    tlf_type=tlf_type,
                    file_path=str(file_path),
                    section_reference=CSRSection.TABLES_FIGURES_LISTINGS,
                    description=f"Auto-detected {tlf_type.value}"
                )
                tlf_items.append(tlf_item)
    
    logger.info(f"Loaded {len(tlf_items)} TLF items")
    return tlf_items


def load_boilerplate_library(boilerplate_file: str) -> Dict[CSRSection, BoilerplateText]:
    """Load boilerplate text library."""
    boilerplate_texts = {}
    
    if not os.path.exists(boilerplate_file):
        logger.warning(f"Boilerplate file not found: {boilerplate_file}. Using defaults.")
        return create_default_boilerplate_library()
    
    with open(boilerplate_file, "r") as f:
        boilerplate_data = json.load(f)
    
    for section_name, text_data in boilerplate_data.items():
        try:
            section = CSRSection(section_name)
            boilerplate = BoilerplateText(
                section=section,
                content=text_data["content"],
                placeholders=text_data.get("placeholders", []),
                is_template=text_data.get("is_template", True)
            )
            boilerplate_texts[section] = boilerplate
        except ValueError:
            logger.warning(f"Unknown CSR section in boilerplate: {section_name}")
    
    logger.info(f"Loaded boilerplate text for {len(boilerplate_texts)} sections")
    return boilerplate_texts


def create_default_boilerplate_library() -> Dict[CSRSection, BoilerplateText]:
    """Create default boilerplate text library."""
    default_boilerplates = {
        CSRSection.SYNOPSIS: BoilerplateText(
            section=CSRSection.SYNOPSIS,
            content="""
            SYNOPSIS
            
            Protocol Number: {protocol_number}
            Protocol Title: {protocol_title}
            
            Study Objectives:
            {primary_objectives}
            
            Study Design: {study_design}
            Study Population: {study_population}
            Sample Size: {sample_size}
            Study Duration: {study_duration}
            
            This clinical study was conducted to evaluate {indication} in {study_population}.
            """,
            placeholders=["protocol_number", "protocol_title", "primary_objectives", 
                         "study_design", "study_population", "sample_size", "study_duration", "indication"]
        ),
        
        CSRSection.INTRODUCTION: BoilerplateText(
            section=CSRSection.INTRODUCTION,
            content="""
            1. INTRODUCTION
            
            1.1 Background and Rationale
            This clinical study was designed to investigate {indication}. The study followed 
            a {study_design} design to evaluate the safety and efficacy of the investigational product.
            
            1.2 Study Rationale
            The rationale for this study was based on previous clinical and non-clinical data 
            supporting the therapeutic potential of the investigational product in {indication}.
            """,
            placeholders=["indication", "study_design"]
        ),
        
        CSRSection.STUDY_OBJECTIVES: BoilerplateText(
            section=CSRSection.STUDY_OBJECTIVES,
            content="""
            2. STUDY OBJECTIVES
            
            2.1 Primary Objectives
            {primary_objectives}
            
            2.2 Secondary Objectives  
            {secondary_objectives}
            
            2.3 Endpoints
            
            2.3.1 Primary Endpoints
            {primary_endpoints}
            
            2.3.2 Secondary Endpoints
            {secondary_endpoints}
            """,
            placeholders=["primary_objectives", "secondary_objectives", "primary_endpoints", "secondary_endpoints"]
        ),
        
        CSRSection.STUDY_SUBJECTS: BoilerplateText(
            section=CSRSection.STUDY_SUBJECTS,
            content="""
            9. STUDY SUBJECTS
            
            9.1 Disposition of Subjects
            A total of {sample_size} subjects were planned for enrollment in this study.
            
            [TABLE: Subject Disposition]
            
            9.2 Demographics and Baseline Characteristics
            Demographics and baseline characteristics are summarized in the tables below.
            
            [TABLE: Demographics and Baseline Characteristics]
            """,
            placeholders=["sample_size"]
        ),
        
        CSRSection.EFFICACY_EVALUATION: BoilerplateText(
            section=CSRSection.EFFICACY_EVALUATION,
            content="""
            10. EFFICACY EVALUATION
            
            10.1 Primary Efficacy Analysis
            The primary efficacy analysis was conducted on the Full Analysis Set (FAS).
            
            [TABLE: Primary Efficacy Results]
            
            10.2 Secondary Efficacy Analyses
            Secondary efficacy analyses were performed to support the primary findings.
            
            [TABLE: Secondary Efficacy Results]
            """,
            placeholders=[]
        ),
        
        CSRSection.SAFETY_EVALUATION: BoilerplateText(
            section=CSRSection.SAFETY_EVALUATION,
            content="""
            11. SAFETY EVALUATION
            
            11.1 Extent of Exposure
            The safety analysis was conducted on the Safety Set.
            
            [TABLE: Extent of Exposure]
            
            11.2 Adverse Events
            Adverse events were coded using MedDRA terminology.
            
            [TABLE: Adverse Events Summary]
            [TABLE: Adverse Events by System Organ Class]
            
            11.3 Serious Adverse Events
            [TABLE: Serious Adverse Events]
            
            11.4 Laboratory Safety
            [TABLE: Laboratory Parameters]
            """,
            placeholders=[]
        ),
        
        CSRSection.DISCUSSION_CONCLUSIONS: BoilerplateText(
            section=CSRSection.DISCUSSION_CONCLUSIONS,
            content="""
            12. DISCUSSION AND CONCLUSIONS
            
            12.1 Summary of Study Results
            This study was conducted to evaluate {indication}. The study met its primary objectives.
            
            12.2 Efficacy Discussion
            The primary efficacy analysis demonstrated [insert findings].
            
            12.3 Safety Discussion
            The safety profile was consistent with previous studies.
            
            12.4 Study Limitations
            [Describe any study limitations]
            
            12.5 Conclusions
            Based on the results of this study, [insert conclusions].
            """,
            placeholders=["indication"]
        )
    }
    
    return default_boilerplates


def generate_section_content(section: CSRSection, protocol_info: ProtocolInfo, 
                           boilerplate: BoilerplateText, tlf_items: List[TLFItem]) -> str:
    """Generate content for a specific CSR section using LLM."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; using template substitution")
        return substitute_placeholders(boilerplate.content, protocol_info, tlf_items)
    
    # Filter TLF items relevant to this section
    relevant_tlfs = [tlf for tlf in tlf_items if tlf.section_reference == section]
    
    prompt = f"""
    You are a regulatory affairs specialist creating a Clinical Study Report (CSR) compliant with ICH E3 guidelines.
    
    Generate content for the {section.value.replace('_', ' ').title()} section of the CSR.
    
    Protocol Information:
    - Protocol Number: {protocol_info.protocol_number}
    - Protocol Title: {protocol_info.protocol_title}
    - Sponsor: {protocol_info.sponsor}
    - Indication: {protocol_info.indication}
    - Study Phase: {protocol_info.study_phase}
    - Study Design: {protocol_info.study_design}
    - Primary Objectives: {protocol_info.primary_objectives}
    - Secondary Objectives: {protocol_info.secondary_objectives}
    - Study Population: {protocol_info.study_population}
    - Sample Size: {protocol_info.sample_size}
    
    Boilerplate Template:
    {boilerplate.content}
    
    Relevant Tables/Figures/Listings:
    {[f"{tlf.tlf_id}: {tlf.title}" for tlf in relevant_tlfs]}
    
    Requirements:
    1. Follow ICH E3 guidelines for CSR structure and content
    2. Use professional medical writing style
    3. Include appropriate placeholders for tables/figures (e.g., [TABLE: Title])
    4. Ensure regulatory compliance
    5. Be concise but comprehensive
    6. Use the boilerplate as a foundation but enhance with specific details
    
    Generate the section content maintaining professional CSR formatting:
    """
    
    try:
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.choices[0].message.content.strip()
        
        # Post-process to ensure proper formatting
        content = substitute_placeholders(content, protocol_info, tlf_items)
        
        logger.info(f"Generated content for section: {section.value}")
        return content
        
    except Exception as e:
        logger.error(f"Failed to generate content for section {section.value}: {e}")
        return substitute_placeholders(boilerplate.content, protocol_info, tlf_items)


def substitute_placeholders(content: str, protocol_info: ProtocolInfo, tlf_items: List[TLFItem]) -> str:
    """Substitute placeholders in content with actual values."""
    # Protocol information substitutions
    substitutions = {
        "protocol_number": protocol_info.protocol_number,
        "protocol_title": protocol_info.protocol_title,
        "sponsor": protocol_info.sponsor,
        "indication": protocol_info.indication,
        "study_phase": protocol_info.study_phase,
        "study_design": protocol_info.study_design,
        "primary_objectives": "\n".join([f"- {obj}" for obj in protocol_info.primary_objectives]),
        "secondary_objectives": "\n".join([f"- {obj}" for obj in protocol_info.secondary_objectives]),
        "primary_endpoints": "\n".join([f"- {ep}" for ep in protocol_info.primary_endpoints]),
        "secondary_endpoints": "\n".join([f"- {ep}" for ep in protocol_info.secondary_endpoints]),
        "study_population": protocol_info.study_population,
        "sample_size": str(protocol_info.sample_size),
        "study_duration": protocol_info.study_duration
    }
    
    # Perform substitutions
    for placeholder, value in substitutions.items():
        content = content.replace(f"{{{placeholder}}}", value)
    
    return content


def insert_tlf_references(content: str, tlf_items: List[TLFItem]) -> str:
    """Insert TLF references into content."""
    # Group TLFs by type
    tables = [tlf for tlf in tlf_items if tlf.tlf_type == TLFType.TABLE]
    figures = [tlf for tlf in tlf_items if tlf.tlf_type == TLFType.FIGURE]
    listings = [tlf for tlf in tlf_items if tlf.tlf_type == TLFType.LISTING]
    
    # Insert table references
    for i, table in enumerate(tables, 1):
        placeholder = f"[TABLE: {table.title}]"
        if placeholder in content:
            reference = f"Table {i}: {table.title}"
            content = content.replace(placeholder, reference)
    
    # Insert figure references
    for i, figure in enumerate(figures, 1):
        placeholder = f"[FIGURE: {figure.title}]"
        if placeholder in content:
            reference = f"Figure {i}: {figure.title}"
            content = content.replace(placeholder, reference)
    
    # Insert listing references
    for i, listing in enumerate(listings, 1):
        placeholder = f"[LISTING: {listing.title}]"
        if placeholder in content:
            reference = f"Listing {i}: {listing.title}"
            content = content.replace(placeholder, reference)
    
    return content


def generate_csr_document(protocol_info: ProtocolInfo, tlf_items: List[TLFItem], 
                         boilerplate_texts: Dict[CSRSection, BoilerplateText]) -> CSRDocument:
    """Generate the complete CSR document."""
    sections = {}
    
    # Define section order for CSR
    section_order = [
        CSRSection.SYNOPSIS,
        CSRSection.INTRODUCTION,
        CSRSection.STUDY_OBJECTIVES,
        CSRSection.INVESTIGATIONAL_PLAN,
        CSRSection.STUDY_SUBJECTS,
        CSRSection.EFFICACY_EVALUATION,
        CSRSection.SAFETY_EVALUATION,
        CSRSection.DISCUSSION_CONCLUSIONS
    ]
    
    for section in section_order:
        if section in boilerplate_texts:
            logger.info(f"Generating content for section: {section.value}")
            content = generate_section_content(section, protocol_info, boilerplate_texts[section], tlf_items)
            content = insert_tlf_references(content, tlf_items)
            sections[section] = content
        else:
            logger.warning(f"No boilerplate found for section: {section.value}")
    
    # Generate metadata
    metadata = {
        "generation_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_sections": len(sections),
        "total_tlfs": len(tlf_items),
        "ich_e3_compliant": True,
        "document_version": "Draft 1.0"
    }
    
    return CSRDocument(
        protocol_info=protocol_info,
        sections=sections,
        tlf_items=tlf_items,
        metadata=metadata,
        generation_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


def save_csr_document(csr_document: CSRDocument, output_dir: str) -> str:
    """Save CSR document to files."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Generate CSR content
    csr_content = f"""
CLINICAL STUDY REPORT

Protocol Number: {csr_document.protocol_info.protocol_number}
Protocol Title: {csr_document.protocol_info.protocol_title}
Sponsor: {csr_document.protocol_info.sponsor}

Generated: {csr_document.generation_timestamp}
Document Version: {csr_document.metadata.get('document_version', 'Draft 1.0')}

{'='*80}

"""
    
    # Add sections in order
    for section, content in csr_document.sections.items():
        csr_content += f"\n\n{content}\n\n"
        csr_content += "-" * 80 + "\n"
    
    # Add TLF appendix
    csr_content += f"""

APPENDIX: TABLES, FIGURES, AND LISTINGS

"""
    
    for i, tlf in enumerate(csr_document.tlf_items, 1):
        csr_content += f"{i}. {tlf.title} ({tlf.tlf_type.value.title()})\n"
        csr_content += f"   File: {tlf.file_path}\n"
        csr_content += f"   Description: {tlf.description}\n\n"
    
    # Save CSR document
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    csr_filename = f"clinical_study_report_{csr_document.protocol_info.protocol_number}_{timestamp}.txt"
    csr_filepath = os.path.join(output_dir, csr_filename)
    
    with open(csr_filepath, "w", encoding="utf-8") as f:
        f.write(csr_content)
    
    # Save CSR metadata
    metadata_filename = f"csr_metadata_{timestamp}.json"
    metadata_filepath = os.path.join(output_dir, metadata_filename)
    
    metadata_export = {
        "protocol_info": {
            "protocol_number": csr_document.protocol_info.protocol_number,
            "protocol_title": csr_document.protocol_info.protocol_title,
            "sponsor": csr_document.protocol_info.sponsor,
            "indication": csr_document.protocol_info.indication,
            "study_phase": csr_document.protocol_info.study_phase,
            "study_design": csr_document.protocol_info.study_design,
            "sample_size": csr_document.protocol_info.sample_size
        },
        "document_metadata": csr_document.metadata,
        "sections_generated": list(csr_document.sections.keys()),
        "tlf_items": [
            {
                "tlf_id": tlf.tlf_id,
                "title": tlf.title,
                "type": tlf.tlf_type.value,
                "file_path": tlf.file_path
            } for tlf in csr_document.tlf_items
        ]
    }
    
    with open(metadata_filepath, "w") as f:
        json.dump(metadata_export, f, indent=2, default=str)
    
    logger.info(f"CSR document saved to {csr_filepath}")
    logger.info(f"CSR metadata saved to {metadata_filepath}")
    
    return csr_filepath


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

    parser = argparse.ArgumentParser(description="Clinical Study Report (CSR) Generation Agent")
    parser.add_argument("protocol_file", help="Path to protocol information JSON file")
    parser.add_argument("--tlf_directory", default="tlf_outputs", help="Directory containing TLF files")
    parser.add_argument("--boilerplate_file", help="Path to boilerplate text library JSON file")
    parser.add_argument("--output_dir", default="output", help="Directory for CSR output")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Load protocol information
    protocol_info = load_protocol_info(args.protocol_file)
    logger.info(f"Loaded protocol: {protocol_info.protocol_number}")

    # Load TLF items
    tlf_items = load_tlf_items(args.tlf_directory)
    
    # Load boilerplate library
    if args.boilerplate_file:
        boilerplate_texts = load_boilerplate_library(args.boilerplate_file)
    else:
        boilerplate_texts = create_default_boilerplate_library()

    # Generate CSR document
    csr_document = generate_csr_document(protocol_info, tlf_items, boilerplate_texts)

    # Save CSR document
    csr_file = save_csr_document(csr_document, args.output_dir)

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    
    summary = f"CSR generation completed: {len(csr_document.sections)} sections generated with {len(tlf_items)} TLF references"
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        summary
    )

    logger.info(f"CSR generation complete: {csr_file}")
    logger.info(f"Protocol: {protocol_info.protocol_title}")
    logger.info(f"Sections: {len(csr_document.sections)}, TLFs: {len(tlf_items)}")


if __name__ == "__main__":
    main()