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

AGENT_ID = "3.300"


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataSource(Enum):
    EDC = "edc"
    PATIENT_APP = "patient_app"
    CALL_CENTER = "call_center"


@dataclass
class SafetyRule:
    """Represents a safety monitoring rule."""
    rule_id: str
    name: str
    keywords: List[str]
    patterns: List[str]
    severity: AlertSeverity
    description: str
    immediate_alert: bool = False


@dataclass
class DataEntry:
    """Represents a data entry from various sources."""
    entry_id: str
    source: DataSource
    subject_id: str
    timestamp: str
    content: str
    metadata: Dict[str, Any]


@dataclass
class SafetyEvent:
    """Represents a detected safety event."""
    event_id: str
    rule_id: str
    subject_id: str
    event_type: str
    description: str
    severity: AlertSeverity
    source: DataSource
    timestamp: str
    confidence: float
    raw_data: str


@dataclass
class SafetyAlert:
    """Represents a safety alert to be sent."""
    alert_id: str
    event_id: str
    subject_id: str
    alert_type: str
    severity: AlertSeverity
    narrative: str
    recipients: List[str]
    delivery_methods: List[str]
    timestamp: str


def load_safety_rules(rules_file: str) -> List[SafetyRule]:
    """Load safety monitoring rules from configuration file."""
    if not os.path.exists(rules_file):
        logger.error(f"Safety rules file not found: {rules_file}")
        return []
    
    with open(rules_file, "r") as f:
        rules_data = json.load(f)
    
    rules = []
    for rule_data in rules_data.get("safety_rules", []):
        rule = SafetyRule(
            rule_id=rule_data["rule_id"],
            name=rule_data["name"],
            keywords=rule_data.get("keywords", []),
            patterns=rule_data.get("patterns", []),
            severity=AlertSeverity(rule_data.get("severity", "medium")),
            description=rule_data["description"],
            immediate_alert=rule_data.get("immediate_alert", False)
        )
        rules.append(rule)
    
    logger.info(f"Loaded {len(rules)} safety rules from {rules_file}")
    return rules


def parse_data_streams(data_sources: Dict[str, Any]) -> List[DataEntry]:
    """Parse data from multiple sources (EDC, patient apps, call center)."""
    entries = []
    
    for source_name, source_data in data_sources.items():
        source_type = DataSource(source_name)
        
        if isinstance(source_data, str) and os.path.exists(source_data):
            with open(source_data, "r") as f:
                source_data = json.load(f)
        
        for record in source_data.get("records", []):
            entry = DataEntry(
                entry_id=record.get("entry_id", f"{source_name}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"),
                source=source_type,
                subject_id=record.get("subject_id", ""),
                timestamp=record.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                content=record.get("content", ""),
                metadata=record.get("metadata", {})
            )
            entries.append(entry)
    
    logger.info(f"Parsed {len(entries)} data entries from {len(data_sources)} sources")
    return entries


def detect_safety_events(data_entries: List[DataEntry], safety_rules: List[SafetyRule]) -> List[SafetyEvent]:
    """Detect potential safety events using rules engine and keyword matching."""
    events = []
    
    for entry in data_entries:
        content_lower = entry.content.lower()
        
        for rule in safety_rules:
            # Check keywords
            keyword_matches = []
            for keyword in rule.keywords:
                if keyword.lower() in content_lower:
                    keyword_matches.append(keyword)
            
            # Check regex patterns
            pattern_matches = []
            for pattern in rule.patterns:
                try:
                    if re.search(pattern, content_lower, re.IGNORECASE):
                        pattern_matches.append(pattern)
                except re.error:
                    logger.warning(f"Invalid regex pattern in rule {rule.rule_id}: {pattern}")
            
            # Calculate confidence based on matches
            total_criteria = len(rule.keywords) + len(rule.patterns)
            matches_found = len(keyword_matches) + len(pattern_matches)
            
            if matches_found > 0:
                confidence = min(matches_found / total_criteria, 1.0)
                
                # Create safety event if confidence threshold met
                if confidence >= 0.3:  # Configurable threshold
                    event = SafetyEvent(
                        event_id=f"SE_{entry.entry_id}_{rule.rule_id}",
                        rule_id=rule.rule_id,
                        subject_id=entry.subject_id,
                        event_type=rule.name,
                        description=f"Potential {rule.name} detected",
                        severity=rule.severity,
                        source=entry.source,
                        timestamp=entry.timestamp,
                        confidence=confidence,
                        raw_data=entry.content
                    )
                    events.append(event)
                    logger.info(f"Safety event detected: {event.event_id} (confidence: {confidence:.2f})")
    
    return events


def generate_safety_narrative(event: SafetyEvent, context_data: Dict[str, Any]) -> str:
    """Generate a safety narrative using LLM."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; generating basic narrative")
        return f"Potential safety event detected: {event.description} for subject {event.subject_id}"
    
    prompt = f"""
    You are a clinical safety specialist. Generate a professional safety event narrative based on the following information:
    
    Event Details:
    - Event ID: {event.event_id}
    - Subject ID: {event.subject_id}
    - Event Type: {event.event_type}
    - Severity: {event.severity.value}
    - Source: {event.source.value}
    - Timestamp: {event.timestamp}
    - Confidence: {event.confidence:.2f}
    - Raw Data: {event.raw_data}
    
    Context Data: {json.dumps(context_data, indent=2)}
    
    Generate a concise but comprehensive safety narrative that includes:
    1. Event description
    2. Clinical significance
    3. Recommended actions
    4. Urgency level
    
    Keep the narrative professional and factual, suitable for regulatory reporting.
    """
    
    try:
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        narrative = response.choices[0].message.content.strip()
        logger.info(f"Generated safety narrative for event {event.event_id}")
        return narrative
        
    except Exception as e:
        logger.error(f"Failed to generate safety narrative: {e}")
        return f"Safety event requiring immediate attention: {event.description} for subject {event.subject_id}. Source: {event.source.value}. Severity: {event.severity.value}."


def create_safety_alerts(events: List[SafetyEvent], alert_config: Dict[str, Any]) -> List[SafetyAlert]:
    """Create safety alerts for detected events."""
    alerts = []
    
    for event in events:
        # Get context data for narrative generation
        context_data = {
            "subject_id": event.subject_id,
            "event_type": event.event_type,
            "source": event.source.value,
            "severity": event.severity.value
        }
        
        # Generate narrative
        narrative = generate_safety_narrative(event, context_data)
        
        # Determine recipients and delivery methods based on severity
        recipients = alert_config.get("recipients", {}).get(event.severity.value, [])
        delivery_methods = alert_config.get("delivery_methods", {}).get(event.severity.value, ["email"])
        
        alert = SafetyAlert(
            alert_id=f"ALERT_{event.event_id}",
            event_id=event.event_id,
            subject_id=event.subject_id,
            alert_type=f"Safety Alert - {event.event_type}",
            severity=event.severity,
            narrative=narrative,
            recipients=recipients,
            delivery_methods=delivery_methods,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        
        alerts.append(alert)
        logger.info(f"Created safety alert: {alert.alert_id}")
    
    return alerts


def send_alert_email(alert: SafetyAlert, email_config: Dict[str, Any]) -> bool:
    """Send safety alert via email (mock implementation)."""
    try:
        # In a real implementation, this would use SMTP or email service API
        logger.info(f"Sending email alert {alert.alert_id} to {alert.recipients}")
        
        email_payload = {
            "to": alert.recipients,
            "subject": f"URGENT: {alert.alert_type} - Subject {alert.subject_id}",
            "body": f"""
            Safety Alert - {alert.severity.value.upper()} Priority
            
            Alert ID: {alert.alert_id}
            Subject ID: {alert.subject_id}
            Event Type: {alert.alert_type}
            Timestamp: {alert.timestamp}
            
            NARRATIVE:
            {alert.narrative}
            
            Please review this safety event immediately and take appropriate action.
            
            This is an automated alert from the Clinical Trial Safety Monitoring System.
            """
        }
        
        logger.debug(f"Email payload: {json.dumps(email_payload, indent=2)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email alert {alert.alert_id}: {e}")
        return False


def send_alert_sms(alert: SafetyAlert, sms_config: Dict[str, Any]) -> bool:
    """Send safety alert via SMS (mock implementation)."""
    try:
        # In a real implementation, this would use SMS service API
        logger.info(f"Sending SMS alert {alert.alert_id} to {alert.recipients}")
        
        sms_message = f"URGENT SAFETY ALERT: {alert.alert_type} for Subject {alert.subject_id}. Alert ID: {alert.alert_id}. Please check email for details."
        
        sms_payload = {
            "to": alert.recipients,
            "message": sms_message
        }
        
        logger.debug(f"SMS payload: {json.dumps(sms_payload, indent=2)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send SMS alert {alert.alert_id}: {e}")
        return False


def dispatch_alerts(alerts: List[SafetyAlert], notification_config: Dict[str, Any]) -> Dict[str, int]:
    """Dispatch safety alerts via configured delivery methods."""
    dispatch_results = {"email": 0, "sms": 0, "failed": 0}
    
    for alert in alerts:
        success = True
        
        if "email" in alert.delivery_methods:
            if send_alert_email(alert, notification_config.get("email", {})):
                dispatch_results["email"] += 1
            else:
                success = False
        
        if "sms" in alert.delivery_methods:
            if send_alert_sms(alert, notification_config.get("sms", {})):
                dispatch_results["sms"] += 1
            else:
                success = False
        
        if not success:
            dispatch_results["failed"] += 1
    
    logger.info(f"Alert dispatch results: {dispatch_results}")
    return dispatch_results


def save_safety_events(events: List[SafetyEvent], output_dir: str) -> str:
    """Save detected safety events to file."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    events_data = []
    for event in events:
        event_dict = {
            "event_id": event.event_id,
            "rule_id": event.rule_id,
            "subject_id": event.subject_id,
            "event_type": event.event_type,
            "description": event.description,
            "severity": event.severity.value,
            "source": event.source.value,
            "timestamp": event.timestamp,
            "confidence": event.confidence,
            "raw_data": event.raw_data
        }
        events_data.append(event_dict)
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    events_file = os.path.join(output_dir, f"safety_events_{timestamp}.json")
    
    with open(events_file, "w") as f:
        json.dump(events_data, f, indent=2)
    
    logger.info(f"Saved {len(events)} safety events to {events_file}")
    return events_file


def save_safety_alerts(alerts: List[SafetyAlert], output_dir: str) -> str:
    """Save safety alerts to file."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    alerts_data = []
    for alert in alerts:
        alert_dict = {
            "alert_id": alert.alert_id,
            "event_id": alert.event_id,
            "subject_id": alert.subject_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity.value,
            "narrative": alert.narrative,
            "recipients": alert.recipients,
            "delivery_methods": alert.delivery_methods,
            "timestamp": alert.timestamp
        }
        alerts_data.append(alert_dict)
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    alerts_file = os.path.join(output_dir, f"safety_alerts_{timestamp}.json")
    
    with open(alerts_file, "w") as f:
        json.dump(alerts_data, f, indent=2)
    
    logger.info(f"Saved {len(alerts)} safety alerts to {alerts_file}")
    return alerts_file


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

    parser = argparse.ArgumentParser(description="Pharmacovigilance & Safety Event Alerting Agent")
    parser.add_argument("safety_rules", help="Path to safety rules configuration file")
    parser.add_argument("--edc_data", help="Path to EDC data feed file")
    parser.add_argument("--patient_app_data", help="Path to patient app data file")
    parser.add_argument("--call_center_data", help="Path to call center logs file")
    parser.add_argument("--alert_config", help="Path to alert configuration file")
    parser.add_argument("--output_dir", default="output", help="Directory for safety output")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Load safety rules
    safety_rules = load_safety_rules(args.safety_rules)
    if not safety_rules:
        logger.error("No safety rules loaded")
        return

    # Parse data streams
    data_sources = {}
    if args.edc_data:
        data_sources["edc"] = args.edc_data
    if args.patient_app_data:
        data_sources["patient_app"] = args.patient_app_data
    if args.call_center_data:
        data_sources["call_center"] = args.call_center_data

    if not data_sources:
        logger.error("No data sources provided")
        return

    data_entries = parse_data_streams(data_sources)
    if not data_entries:
        logger.error("No data entries parsed")
        return

    # Detect safety events
    safety_events = detect_safety_events(data_entries, safety_rules)
    save_safety_events(safety_events, args.output_dir)

    # Create and dispatch alerts
    if safety_events:
        # Load alert configuration
        alert_config = {}
        if args.alert_config and os.path.exists(args.alert_config):
            with open(args.alert_config, "r") as f:
                alert_config = json.load(f)
        else:
            # Default configuration
            alert_config = {
                "recipients": {
                    "critical": ["safety@example.com", "cro@example.com"],
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

        safety_alerts = create_safety_alerts(safety_events, alert_config)
        save_safety_alerts(safety_alerts, args.output_dir)
        
        # Dispatch alerts
        dispatch_results = dispatch_alerts(safety_alerts, alert_config)
        logger.info(f"Alert dispatching completed: {dispatch_results}")

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    
    summary = f"Safety monitoring completed: {len(data_entries)} entries processed, {len(safety_events)} events detected"
    if safety_events:
        summary += f", {len(safety_alerts)} alerts sent"
    
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        summary
    )

    logger.info(f"Pharmacovigilance processing complete: {len(safety_events)} safety events detected")


if __name__ == "__main__":
    main()