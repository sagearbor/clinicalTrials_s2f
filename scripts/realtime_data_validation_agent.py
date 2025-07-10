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

AGENT_ID = "3.100"


class ValidationResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class ValidationRule:
    """Represents a data validation rule."""
    rule_id: str
    rule_type: str  # range, logical, format, required, etc.
    field_name: str
    description: str
    parameters: Dict[str, Any]
    severity: str  # critical, major, minor


@dataclass
class DataPoint:
    """Represents a single data point from EDC."""
    subject_id: str
    visit_name: str
    form_name: str
    field_name: str
    value: Any
    timestamp: str
    data_type: str


@dataclass
class ValidationIssue:
    """Represents a validation issue found."""
    issue_id: str
    rule_id: str
    subject_id: str
    field_name: str
    issue_description: str
    severity: str
    suggested_action: str
    timestamp: str


def load_validation_plan(plan_file: str) -> List[ValidationRule]:
    """Load validation rules from the Data Validation Plan file."""
    if not os.path.exists(plan_file):
        logger.error(f"Validation plan file not found: {plan_file}")
        return []
    
    with open(plan_file, "r") as f:
        plan_data = json.load(f)
    
    rules = []
    for rule_data in plan_data.get("validation_rules", []):
        rule = ValidationRule(
            rule_id=rule_data["rule_id"],
            rule_type=rule_data["rule_type"],
            field_name=rule_data["field_name"],
            description=rule_data["description"],
            parameters=rule_data.get("parameters", {}),
            severity=rule_data.get("severity", "major")
        )
        rules.append(rule)
    
    logger.info(f"Loaded {len(rules)} validation rules from {plan_file}")
    return rules


def parse_edc_data(data_feed: Union[str, Dict[str, Any]]) -> List[DataPoint]:
    """Parse incoming EDC data feed into structured data points."""
    if isinstance(data_feed, str):
        if os.path.exists(data_feed):
            with open(data_feed, "r") as f:
                data_feed = json.load(f)
        else:
            try:
                data_feed = json.loads(data_feed)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in data feed")
                return []
    
    data_points = []
    for record in data_feed.get("records", []):
        for field_name, field_value in record.get("fields", {}).items():
            data_point = DataPoint(
                subject_id=record.get("subject_id", ""),
                visit_name=record.get("visit_name", ""),
                form_name=record.get("form_name", ""),
                field_name=field_name,
                value=field_value,
                timestamp=record.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                data_type=record.get("data_types", {}).get(field_name, "string")
            )
            data_points.append(data_point)
    
    logger.info(f"Parsed {len(data_points)} data points from EDC feed")
    return data_points


def validate_range_check(data_point: DataPoint, rule: ValidationRule) -> Optional[ValidationIssue]:
    """Perform range validation on numeric data."""
    if rule.rule_type != "range":
        return None
    
    try:
        value = float(data_point.value) if data_point.value is not None else None
        if value is None:
            return None
        
        min_val = rule.parameters.get("min")
        max_val = rule.parameters.get("max")
        
        if min_val is not None and value < min_val:
            return ValidationIssue(
                issue_id=f"{rule.rule_id}_{data_point.subject_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
                rule_id=rule.rule_id,
                subject_id=data_point.subject_id,
                field_name=data_point.field_name,
                issue_description=f"Value {value} is below minimum threshold {min_val}",
                severity=rule.severity,
                suggested_action=f"Verify {data_point.field_name} value for subject {data_point.subject_id}",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
        
        if max_val is not None and value > max_val:
            return ValidationIssue(
                issue_id=f"{rule.rule_id}_{data_point.subject_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
                rule_id=rule.rule_id,
                subject_id=data_point.subject_id,
                field_name=data_point.field_name,
                issue_description=f"Value {value} is above maximum threshold {max_val}",
                severity=rule.severity,
                suggested_action=f"Verify {data_point.field_name} value for subject {data_point.subject_id}",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
    
    except (ValueError, TypeError):
        return ValidationIssue(
            issue_id=f"{rule.rule_id}_{data_point.subject_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
            rule_id=rule.rule_id,
            subject_id=data_point.subject_id,
            field_name=data_point.field_name,
            issue_description=f"Non-numeric value '{data_point.value}' in numeric field",
            severity=rule.severity,
            suggested_action=f"Correct data type for {data_point.field_name}",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
    
    return None


def validate_required_check(data_point: DataPoint, rule: ValidationRule) -> Optional[ValidationIssue]:
    """Check if required fields are present and not empty."""
    if rule.rule_type != "required":
        return None
    
    if data_point.value is None or data_point.value == "" or data_point.value == []:
        return ValidationIssue(
            issue_id=f"{rule.rule_id}_{data_point.subject_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
            rule_id=rule.rule_id,
            subject_id=data_point.subject_id,
            field_name=data_point.field_name,
            issue_description=f"Required field '{data_point.field_name}' is missing or empty",
            severity=rule.severity,
            suggested_action=f"Provide value for required field {data_point.field_name}",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
    
    return None


def validate_logical_check(data_point: DataPoint, rule: ValidationRule, all_data_points: List[DataPoint]) -> Optional[ValidationIssue]:
    """Perform logical validation using LLM for complex business rules."""
    if rule.rule_type != "logical":
        return None
    
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; skipping logical validation")
        return None
    
    # Get related data points for the same subject
    subject_data = [dp for dp in all_data_points if dp.subject_id == data_point.subject_id]
    
    # Create context for LLM
    context = {
        "current_field": data_point.field_name,
        "current_value": data_point.value,
        "subject_data": {dp.field_name: dp.value for dp in subject_data},
        "rule_description": rule.description,
        "rule_parameters": rule.parameters
    }
    
    prompt = f"""
    You are a clinical data validation expert. Review the following data point against the logical validation rule:
    
    Context: {json.dumps(context, indent=2)}
    
    Determine if this data point violates the logical rule. Consider:
    1. Business logic consistency
    2. Cross-field dependencies
    3. Clinical feasibility
    
    Response format (JSON):
    {{
        "violation_found": true/false,
        "issue_description": "description of the issue if found",
        "suggested_action": "recommended corrective action",
        "confidence": 0.0-1.0
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
            
            if result.get("violation_found") and result.get("confidence", 0) > 0.7:
                return ValidationIssue(
                    issue_id=f"{rule.rule_id}_{data_point.subject_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
                    rule_id=rule.rule_id,
                    subject_id=data_point.subject_id,
                    field_name=data_point.field_name,
                    issue_description=result.get("issue_description", "Logical validation failed"),
                    severity=rule.severity,
                    suggested_action=result.get("suggested_action", "Review data for logical consistency"),
                    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                )
        
    except Exception as e:
        logger.error(f"Logical validation failed: {e}")
    
    return None


def validate_format_check(data_point: DataPoint, rule: ValidationRule) -> Optional[ValidationIssue]:
    """Validate data format using regex patterns."""
    if rule.rule_type != "format":
        return None
    
    import re
    
    pattern = rule.parameters.get("pattern")
    if not pattern:
        return None
    
    try:
        if not re.match(pattern, str(data_point.value)):
            return ValidationIssue(
                issue_id=f"{rule.rule_id}_{data_point.subject_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
                rule_id=rule.rule_id,
                subject_id=data_point.subject_id,
                field_name=data_point.field_name,
                issue_description=f"Value '{data_point.value}' does not match required format pattern",
                severity=rule.severity,
                suggested_action=f"Correct format for {data_point.field_name}",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
    except re.error:
        logger.error(f"Invalid regex pattern in rule {rule.rule_id}")
    
    return None


def run_validation_checks(data_points: List[DataPoint], validation_rules: List[ValidationRule]) -> List[ValidationIssue]:
    """Run all validation checks on the data points."""
    issues = []
    
    for data_point in data_points:
        # Find applicable rules for this field
        applicable_rules = [rule for rule in validation_rules if rule.field_name == data_point.field_name or rule.field_name == "*"]
        
        for rule in applicable_rules:
            issue = None
            
            if rule.rule_type == "range":
                issue = validate_range_check(data_point, rule)
            elif rule.rule_type == "required":
                issue = validate_required_check(data_point, rule)
            elif rule.rule_type == "logical":
                issue = validate_logical_check(data_point, rule, data_points)
            elif rule.rule_type == "format":
                issue = validate_format_check(data_point, rule)
            
            if issue:
                issues.append(issue)
    
    logger.info(f"Found {len(issues)} validation issues")
    return issues


def create_data_queries(issues: List[ValidationIssue], output_dir: str) -> List[str]:
    """Create automated data queries for EDC system."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    queries = []
    for issue in issues:
        query = {
            "query_id": f"DQ_{issue.issue_id}",
            "subject_id": issue.subject_id,
            "field_name": issue.field_name,
            "query_type": "data_validation",
            "priority": issue.severity,
            "query_text": f"Data Validation Issue: {issue.issue_description}",
            "suggested_resolution": issue.suggested_action,
            "created_timestamp": issue.timestamp,
            "status": "open"
        }
        queries.append(query)
    
    # Save queries to file
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    queries_file = os.path.join(output_dir, f"data_queries_{timestamp}.json")
    
    with open(queries_file, "w") as f:
        json.dump(queries, f, indent=2)
    
    logger.info(f"Created {len(queries)} data queries saved to {queries_file}")
    return queries


def save_validation_report(data_points: List[DataPoint], issues: List[ValidationIssue], output_dir: str) -> str:
    """Save comprehensive validation report."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    report = {
        "validation_summary": {
            "total_data_points": len(data_points),
            "total_issues": len(issues),
            "critical_issues": len([i for i in issues if i.severity == "critical"]),
            "major_issues": len([i for i in issues if i.severity == "major"]),
            "minor_issues": len([i for i in issues if i.severity == "minor"]),
            "validation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        },
        "issues": [
            {
                "issue_id": issue.issue_id,
                "rule_id": issue.rule_id,
                "subject_id": issue.subject_id,
                "field_name": issue.field_name,
                "description": issue.issue_description,
                "severity": issue.severity,
                "suggested_action": issue.suggested_action,
                "timestamp": issue.timestamp
            } for issue in issues
        ]
    }
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    report_file = os.path.join(output_dir, f"validation_report_{timestamp}.json")
    
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Validation report saved to {report_file}")
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

    parser = argparse.ArgumentParser(description="Real-time Data Validation Agent")
    parser.add_argument("validation_plan", help="Path to Data Validation Plan JSON file")
    parser.add_argument("data_feed", help="Path to EDC data feed JSON file or JSON string")
    parser.add_argument("--output_dir", default="output", help="Directory for validation output")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Load validation rules
    validation_rules = load_validation_plan(args.validation_plan)
    if not validation_rules:
        logger.error("No validation rules loaded")
        return

    # Parse EDC data
    data_points = parse_edc_data(args.data_feed)
    if not data_points:
        logger.error("No data points parsed from EDC feed")
        return

    # Run validation checks
    issues = run_validation_checks(data_points, validation_rules)

    # Create data queries for EDC system
    queries = create_data_queries(issues, args.output_dir)

    # Save validation report
    report_file = save_validation_report(data_points, issues, args.output_dir)

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        f"Real-time data validation completed: {len(data_points)} data points processed, {len(issues)} issues found"
    )

    logger.info(f"Validation complete: {len(issues)} issues found and {len(queries)} queries created")


if __name__ == "__main__":
    main()