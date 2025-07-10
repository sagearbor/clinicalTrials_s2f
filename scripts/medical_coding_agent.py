import os
import json
import logging
import datetime
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

AGENT_ID = "3.200"


class CodingSystem(Enum):
    MEDDRA = "meddra"
    ICD10 = "icd10"
    WHODD = "whodd"
    SNOMED = "snomed"


class TermType(Enum):
    ADVERSE_EVENT = "adverse_event"
    MEDICATION = "medication"
    MEDICAL_HISTORY = "medical_history"
    INDICATION = "indication"


@dataclass
class UncodedTerm:
    """Represents an uncoded medical term from EDC."""
    term_id: str
    original_text: str
    term_type: TermType
    subject_id: str
    visit_name: str
    form_name: str
    field_name: str
    verbatim_term: str
    context: str
    timestamp: str


@dataclass
class MedicalCode:
    """Represents a medical code suggestion."""
    code: str
    preferred_term: str
    system_organ_class: str
    coding_system: CodingSystem
    level: str
    confidence_score: float
    reasoning: str


@dataclass
class CodingSuggestion:
    """Represents a coding suggestion for a term."""
    term_id: str
    original_text: str
    suggested_codes: List[MedicalCode]
    primary_suggestion: MedicalCode
    alternative_suggestions: List[MedicalCode]
    coding_timestamp: str
    reviewer_notes: str


def load_coding_dictionaries(dictionaries_dir: str) -> Dict[CodingSystem, Dict[str, Any]]:
    """Load medical coding dictionaries from files."""
    dictionaries = {}
    
    for coding_system in CodingSystem:
        dict_file = os.path.join(dictionaries_dir, f"{coding_system.value}_dictionary.json")
        
        if os.path.exists(dict_file):
            with open(dict_file, "r") as f:
                dictionaries[coding_system] = json.load(f)
            logger.info(f"Loaded {coding_system.value} dictionary with {len(dictionaries[coding_system].get('terms', []))} terms")
        else:
            logger.warning(f"Dictionary file not found: {dict_file}")
            # Create basic fallback dictionary
            dictionaries[coding_system] = {
                "terms": [],
                "hierarchy": {},
                "synonyms": {}
            }
    
    return dictionaries


def parse_uncoded_terms(terms_data: Union[str, Dict[str, Any]]) -> List[UncodedTerm]:
    """Parse uncoded terms from EDC data."""
    if isinstance(terms_data, str) and os.path.exists(terms_data):
        with open(terms_data, "r") as f:
            terms_data = json.load(f)
    
    terms = []
    for term_data in terms_data.get("uncoded_terms", []):
        term = UncodedTerm(
            term_id=term_data.get("term_id", f"TERM_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"),
            original_text=term_data.get("original_text", ""),
            term_type=TermType(term_data.get("term_type", "adverse_event")),
            subject_id=term_data.get("subject_id", ""),
            visit_name=term_data.get("visit_name", ""),
            form_name=term_data.get("form_name", ""),
            field_name=term_data.get("field_name", ""),
            verbatim_term=term_data.get("verbatim_term", term_data.get("original_text", "")),
            context=term_data.get("context", ""),
            timestamp=term_data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())
        )
        terms.append(term)
    
    logger.info(f"Parsed {len(terms)} uncoded terms")
    return terms


def dictionary_lookup(term: UncodedTerm, dictionaries: Dict[CodingSystem, Dict[str, Any]]) -> List[MedicalCode]:
    """Perform dictionary-based lookup for medical codes."""
    matches = []
    search_text = term.verbatim_term.lower().strip()
    
    for coding_system, dictionary in dictionaries.items():
        # Direct term matching
        for dict_term in dictionary.get("terms", []):
            preferred_term = dict_term.get("preferred_term", "").lower()
            synonyms = [s.lower() for s in dict_term.get("synonyms", [])]
            
            # Check for exact match
            if search_text == preferred_term or search_text in synonyms:
                code = MedicalCode(
                    code=dict_term.get("code", ""),
                    preferred_term=dict_term.get("preferred_term", ""),
                    system_organ_class=dict_term.get("system_organ_class", ""),
                    coding_system=coding_system,
                    level=dict_term.get("level", "PT"),
                    confidence_score=0.95,
                    reasoning="Exact dictionary match"
                )
                matches.append(code)
            
            # Check for partial match
            elif search_text in preferred_term or any(search_text in syn for syn in synonyms):
                code = MedicalCode(
                    code=dict_term.get("code", ""),
                    preferred_term=dict_term.get("preferred_term", ""),
                    system_organ_class=dict_term.get("system_organ_class", ""),
                    coding_system=coding_system,
                    level=dict_term.get("level", "PT"),
                    confidence_score=0.75,
                    reasoning="Partial dictionary match"
                )
                matches.append(code)
    
    # Sort by confidence score
    matches.sort(key=lambda x: x.confidence_score, reverse=True)
    return matches[:10]  # Return top 10 matches


def llm_medical_coding(term: UncodedTerm, coding_system: CodingSystem = CodingSystem.MEDDRA) -> List[MedicalCode]:
    """Use LLM to suggest medical codes."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; skipping LLM coding")
        return []
    
    prompt = f"""
    You are a medical coding specialist. Your task is to suggest appropriate {coding_system.value.upper()} codes for the given medical term.
    
    Term Details:
    - Original Text: {term.original_text}
    - Verbatim Term: {term.verbatim_term}
    - Term Type: {term.term_type.value}
    - Context: {term.context}
    - Subject ID: {term.subject_id}
    - Visit: {term.visit_name}
    - Form: {term.form_name}
    
    Please provide up to 3 most appropriate {coding_system.value.upper()} codes in JSON format:
    {{
        "suggestions": [
            {{
                "code": "10012345",
                "preferred_term": "Headache",
                "system_organ_class": "Nervous system disorders",
                "level": "PT",
                "confidence_score": 0.90,
                "reasoning": "Direct match for common adverse event"
            }}
        ]
    }}
    
    Consider:
    1. Clinical context and terminology
    2. Severity and specificity
    3. Anatomical location if applicable
    4. Standard medical terminology
    5. Regulatory requirements for clinical trials
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
            
            codes = []
            for suggestion in result.get("suggestions", []):
                code = MedicalCode(
                    code=suggestion.get("code", ""),
                    preferred_term=suggestion.get("preferred_term", ""),
                    system_organ_class=suggestion.get("system_organ_class", ""),
                    coding_system=coding_system,
                    level=suggestion.get("level", "PT"),
                    confidence_score=suggestion.get("confidence_score", 0.5),
                    reasoning=suggestion.get("reasoning", "LLM suggestion")
                )
                codes.append(code)
            
            logger.info(f"LLM generated {len(codes)} coding suggestions for term: {term.verbatim_term}")
            return codes
        
    except Exception as e:
        logger.error(f"LLM coding failed for term {term.term_id}: {e}")
    
    return []


def combine_coding_suggestions(dict_matches: List[MedicalCode], llm_matches: List[MedicalCode]) -> List[MedicalCode]:
    """Combine and deduplicate coding suggestions from different sources."""
    all_suggestions = dict_matches + llm_matches
    
    # Remove duplicates based on code
    seen_codes = set()
    unique_suggestions = []
    
    for suggestion in all_suggestions:
        if suggestion.code not in seen_codes:
            seen_codes.add(suggestion.code)
            unique_suggestions.append(suggestion)
    
    # Sort by confidence score
    unique_suggestions.sort(key=lambda x: x.confidence_score, reverse=True)
    
    return unique_suggestions


def create_coding_suggestion(term: UncodedTerm, all_codes: List[MedicalCode]) -> CodingSuggestion:
    """Create a coding suggestion from available codes."""
    if not all_codes:
        # Create a placeholder suggestion if no codes found
        placeholder_code = MedicalCode(
            code="UNCODED",
            preferred_term=term.verbatim_term,
            system_organ_class="Unspecified",
            coding_system=CodingSystem.MEDDRA,
            level="PT",
            confidence_score=0.0,
            reasoning="No suitable code found - requires manual review"
        )
        all_codes = [placeholder_code]
    
    primary_suggestion = all_codes[0]
    alternative_suggestions = all_codes[1:5]  # Top 4 alternatives
    
    return CodingSuggestion(
        term_id=term.term_id,
        original_text=term.original_text,
        suggested_codes=all_codes,
        primary_suggestion=primary_suggestion,
        alternative_suggestions=alternative_suggestions,
        coding_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        reviewer_notes=""
    )


def process_medical_coding(terms: List[UncodedTerm], dictionaries: Dict[CodingSystem, Dict[str, Any]], 
                          use_llm: bool = True) -> List[CodingSuggestion]:
    """Process medical coding for all terms."""
    suggestions = []
    
    for term in terms:
        logger.info(f"Processing term: {term.verbatim_term} (Type: {term.term_type.value})")
        
        # Dictionary-based lookup
        dict_matches = dictionary_lookup(term, dictionaries)
        
        # LLM-based coding
        llm_matches = []
        if use_llm:
            llm_matches = llm_medical_coding(term)
        
        # Combine suggestions
        all_codes = combine_coding_suggestions(dict_matches, llm_matches)
        
        # Create coding suggestion
        suggestion = create_coding_suggestion(term, all_codes)
        suggestions.append(suggestion)
        
        logger.info(f"Generated {len(all_codes)} coding suggestions for term: {term.verbatim_term}")
    
    return suggestions


def generate_coding_report(suggestions: List[CodingSuggestion], output_dir: str) -> str:
    """Generate a comprehensive coding report."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    report_data = {
        "coding_summary": {
            "total_terms": len(suggestions),
            "high_confidence_codes": len([s for s in suggestions if s.primary_suggestion.confidence_score >= 0.8]),
            "medium_confidence_codes": len([s for s in suggestions if 0.5 <= s.primary_suggestion.confidence_score < 0.8]),
            "low_confidence_codes": len([s for s in suggestions if s.primary_suggestion.confidence_score < 0.5]),
            "uncoded_terms": len([s for s in suggestions if s.primary_suggestion.code == "UNCODED"]),
            "report_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        },
        "coding_suggestions": [
            {
                "term_id": suggestion.term_id,
                "original_text": suggestion.original_text,
                "primary_suggestion": {
                    "code": suggestion.primary_suggestion.code,
                    "preferred_term": suggestion.primary_suggestion.preferred_term,
                    "system_organ_class": suggestion.primary_suggestion.system_organ_class,
                    "coding_system": suggestion.primary_suggestion.coding_system.value,
                    "level": suggestion.primary_suggestion.level,
                    "confidence_score": suggestion.primary_suggestion.confidence_score,
                    "reasoning": suggestion.primary_suggestion.reasoning
                },
                "alternative_suggestions": [
                    {
                        "code": alt.code,
                        "preferred_term": alt.preferred_term,
                        "confidence_score": alt.confidence_score,
                        "reasoning": alt.reasoning
                    } for alt in suggestion.alternative_suggestions
                ],
                "coding_timestamp": suggestion.coding_timestamp
            } for suggestion in suggestions
        ],
        "statistics": {
            "coding_systems_used": list(set(s.primary_suggestion.coding_system.value for s in suggestions)),
            "term_types_processed": list(set(s.original_text for s in suggestions)),
            "avg_confidence_score": sum(s.primary_suggestion.confidence_score for s in suggestions) / len(suggestions) if suggestions else 0
        }
    }
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    report_file = os.path.join(output_dir, f"medical_coding_report_{timestamp}.json")
    
    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=2)
    
    logger.info(f"Medical coding report saved to {report_file}")
    return report_file


def export_for_review(suggestions: List[CodingSuggestion], output_dir: str) -> str:
    """Export coding suggestions in format suitable for human review."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    review_data = []
    for suggestion in suggestions:
        review_item = {
            "term_id": suggestion.term_id,
            "original_text": suggestion.original_text,
            "suggested_code": suggestion.primary_suggestion.code,
            "suggested_term": suggestion.primary_suggestion.preferred_term,
            "confidence": suggestion.primary_suggestion.confidence_score,
            "system_organ_class": suggestion.primary_suggestion.system_organ_class,
            "coding_system": suggestion.primary_suggestion.coding_system.value,
            "reasoning": suggestion.primary_suggestion.reasoning,
            "review_status": "pending",
            "reviewer_comments": "",
            "final_code": "",
            "final_term": ""
        }
        review_data.append(review_item)
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    review_file = os.path.join(output_dir, f"coding_review_queue_{timestamp}.json")
    
    with open(review_file, "w") as f:
        json.dump(review_data, f, indent=2)
    
    logger.info(f"Coding review queue exported to {review_file}")
    return review_file


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

    parser = argparse.ArgumentParser(description="Medical Coding Agent")
    parser.add_argument("terms_data", help="Path to uncoded terms data file")
    parser.add_argument("--dictionaries_dir", default="dictionaries", help="Directory containing medical coding dictionaries")
    parser.add_argument("--use_llm", action="store_true", help="Use LLM for additional coding suggestions")
    parser.add_argument("--output_dir", default="output", help="Directory for coding output")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Load medical coding dictionaries
    dictionaries = load_coding_dictionaries(args.dictionaries_dir)

    # Parse uncoded terms
    terms = parse_uncoded_terms(args.terms_data)
    if not terms:
        logger.error("No uncoded terms found")
        return

    # Process medical coding
    suggestions = process_medical_coding(terms, dictionaries, args.use_llm)

    # Generate reports
    coding_report = generate_coding_report(suggestions, args.output_dir)
    review_queue = export_for_review(suggestions, args.output_dir)

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    
    high_confidence = len([s for s in suggestions if s.primary_suggestion.confidence_score >= 0.8])
    summary = f"Medical coding completed: {len(suggestions)} terms processed, {high_confidence} high-confidence codes generated"
    
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        summary
    )

    logger.info(f"Medical coding complete: {len(suggestions)} terms coded with {high_confidence} high-confidence suggestions")


if __name__ == "__main__":
    main()