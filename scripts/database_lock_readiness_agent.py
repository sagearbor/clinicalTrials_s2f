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

AGENT_ID = "4.100"


class ActivityStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class ActivityCategory(Enum):
    DATA_QUERIES = "data_queries"
    SAFETY_EVENTS = "safety_events"
    MONITORING_VISITS = "monitoring_visits"
    DATA_CLEANING = "data_cleaning"
    REGULATORY = "regulatory"
    STATISTICAL = "statistical"


@dataclass
class CloseoutActivity:
    """Represents a database lock closeout activity."""
    activity_id: str
    name: str
    description: str
    category: ActivityCategory
    status: ActivityStatus
    completion_percentage: float
    estimated_days_remaining: int
    dependencies: List[str]
    assigned_to: str
    priority: str
    last_updated: str
    notes: str


@dataclass
class QueryStatus:
    """Represents the status of data queries."""
    total_queries: int
    open_queries: int
    closed_queries: int
    overdue_queries: int
    avg_resolution_days: float
    critical_queries: int


@dataclass
class SafetyEventStatus:
    """Represents the status of safety events."""
    total_events: int
    reconciled_events: int
    pending_events: int
    serious_events: int
    resolved_events: int
    avg_resolution_days: float


@dataclass
class MonitoringVisitStatus:
    """Represents the status of monitoring visits."""
    total_sites: int
    completed_visits: int
    pending_visits: int
    overdue_visits: int
    avg_visit_duration: float
    critical_findings: int


@dataclass
class ReadinessAssessment:
    """Represents the overall database lock readiness assessment."""
    overall_readiness_percentage: float
    projected_lock_date: str
    critical_blockers: List[str]
    risk_factors: List[str]
    recommendations: List[str]
    confidence_level: str


def load_closeout_activities(activities_file: str) -> List[CloseoutActivity]:
    """Load closeout activities from configuration file."""
    if not os.path.exists(activities_file):
        logger.error(f"Activities file not found: {activities_file}")
        return []
    
    with open(activities_file, "r") as f:
        activities_data = json.load(f)
    
    activities = []
    for activity_data in activities_data.get("closeout_activities", []):
        activity = CloseoutActivity(
            activity_id=activity_data["activity_id"],
            name=activity_data["name"],
            description=activity_data["description"],
            category=ActivityCategory(activity_data["category"]),
            status=ActivityStatus(activity_data.get("status", "not_started")),
            completion_percentage=activity_data.get("completion_percentage", 0.0),
            estimated_days_remaining=activity_data.get("estimated_days_remaining", 0),
            dependencies=activity_data.get("dependencies", []),
            assigned_to=activity_data.get("assigned_to", ""),
            priority=activity_data.get("priority", "medium"),
            last_updated=activity_data.get("last_updated", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            notes=activity_data.get("notes", "")
        )
        activities.append(activity)
    
    logger.info(f"Loaded {len(activities)} closeout activities from {activities_file}")
    return activities


def analyze_query_status(query_data: Dict[str, Any]) -> QueryStatus:
    """Analyze data query status from input data."""
    if isinstance(query_data, str) and os.path.exists(query_data):
        with open(query_data, "r") as f:
            query_data = json.load(f)
    
    queries = query_data.get("queries", [])
    total_queries = len(queries)
    open_queries = len([q for q in queries if q.get("status") == "open"])
    closed_queries = len([q for q in queries if q.get("status") == "closed"])
    overdue_queries = len([q for q in queries if q.get("overdue", False)])
    critical_queries = len([q for q in queries if q.get("priority") == "critical"])
    
    # Calculate average resolution days
    resolved_queries = [q for q in queries if q.get("status") == "closed" and q.get("resolution_days")]
    avg_resolution_days = sum(q.get("resolution_days", 0) for q in resolved_queries) / len(resolved_queries) if resolved_queries else 0
    
    return QueryStatus(
        total_queries=total_queries,
        open_queries=open_queries,
        closed_queries=closed_queries,
        overdue_queries=overdue_queries,
        avg_resolution_days=avg_resolution_days,
        critical_queries=critical_queries
    )


def analyze_safety_event_status(safety_data: Dict[str, Any]) -> SafetyEventStatus:
    """Analyze safety event status from input data."""
    if isinstance(safety_data, str) and os.path.exists(safety_data):
        with open(safety_data, "r") as f:
            safety_data = json.load(f)
    
    events = safety_data.get("safety_events", [])
    total_events = len(events)
    reconciled_events = len([e for e in events if e.get("reconciled", False)])
    pending_events = len([e for e in events if e.get("status") == "pending"])
    serious_events = len([e for e in events if e.get("serious", False)])
    resolved_events = len([e for e in events if e.get("status") == "resolved"])
    
    # Calculate average resolution days
    resolved_list = [e for e in events if e.get("status") == "resolved" and e.get("resolution_days")]
    avg_resolution_days = sum(e.get("resolution_days", 0) for e in resolved_list) / len(resolved_list) if resolved_list else 0
    
    return SafetyEventStatus(
        total_events=total_events,
        reconciled_events=reconciled_events,
        pending_events=pending_events,
        serious_events=serious_events,
        resolved_events=resolved_events,
        avg_resolution_days=avg_resolution_days
    )


def analyze_monitoring_visit_status(monitoring_data: Dict[str, Any]) -> MonitoringVisitStatus:
    """Analyze monitoring visit status from input data."""
    if isinstance(monitoring_data, str) and os.path.exists(monitoring_data):
        with open(monitoring_data, "r") as f:
            monitoring_data = json.load(f)
    
    visits = monitoring_data.get("monitoring_visits", [])
    sites = monitoring_data.get("sites", [])
    
    total_sites = len(sites)
    completed_visits = len([v for v in visits if v.get("status") == "completed"])
    pending_visits = len([v for v in visits if v.get("status") == "pending"])
    overdue_visits = len([v for v in visits if v.get("overdue", False)])
    critical_findings = len([v for v in visits if v.get("critical_findings", 0) > 0])
    
    # Calculate average visit duration
    completed_list = [v for v in visits if v.get("status") == "completed" and v.get("duration_days")]
    avg_visit_duration = sum(v.get("duration_days", 0) for v in completed_list) / len(completed_list) if completed_list else 0
    
    return MonitoringVisitStatus(
        total_sites=total_sites,
        completed_visits=completed_visits,
        pending_visits=pending_visits,
        overdue_visits=overdue_visits,
        avg_visit_duration=avg_visit_duration,
        critical_findings=critical_findings
    )


def update_activity_status(activities: List[CloseoutActivity], status_data: Dict[str, Any]) -> List[CloseoutActivity]:
    """Update activity status based on current data."""
    query_status = status_data.get("query_status")
    safety_status = status_data.get("safety_status")
    monitoring_status = status_data.get("monitoring_status")
    
    for activity in activities:
        if activity.category == ActivityCategory.DATA_QUERIES and query_status:
            # Update data query related activities
            if query_status.open_queries == 0:
                activity.status = ActivityStatus.COMPLETED
                activity.completion_percentage = 100.0
                activity.estimated_days_remaining = 0
            elif query_status.critical_queries > 0:
                activity.status = ActivityStatus.BLOCKED
                activity.estimated_days_remaining = max(query_status.avg_resolution_days * query_status.critical_queries, 5)
            else:
                activity.status = ActivityStatus.IN_PROGRESS
                activity.completion_percentage = (query_status.closed_queries / query_status.total_queries) * 100
                activity.estimated_days_remaining = int(query_status.avg_resolution_days * query_status.open_queries)
        
        elif activity.category == ActivityCategory.SAFETY_EVENTS and safety_status:
            # Update safety event related activities
            if safety_status.pending_events == 0:
                activity.status = ActivityStatus.COMPLETED
                activity.completion_percentage = 100.0
                activity.estimated_days_remaining = 0
            else:
                activity.status = ActivityStatus.IN_PROGRESS
                activity.completion_percentage = (safety_status.resolved_events / safety_status.total_events) * 100
                activity.estimated_days_remaining = int(safety_status.avg_resolution_days * safety_status.pending_events)
        
        elif activity.category == ActivityCategory.MONITORING_VISITS and monitoring_status:
            # Update monitoring visit related activities
            if monitoring_status.pending_visits == 0:
                activity.status = ActivityStatus.COMPLETED
                activity.completion_percentage = 100.0
                activity.estimated_days_remaining = 0
            else:
                activity.status = ActivityStatus.IN_PROGRESS
                activity.completion_percentage = (monitoring_status.completed_visits / monitoring_status.total_sites) * 100
                activity.estimated_days_remaining = int(monitoring_status.avg_visit_duration * monitoring_status.pending_visits)
        
        activity.last_updated = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    return activities


def calculate_readiness_assessment(activities: List[CloseoutActivity], status_data: Dict[str, Any]) -> ReadinessAssessment:
    """Calculate overall database lock readiness assessment."""
    # Calculate overall readiness percentage
    total_activities = len(activities)
    if total_activities == 0:
        overall_readiness = 0.0
    else:
        total_completion = sum(activity.completion_percentage for activity in activities)
        overall_readiness = total_completion / total_activities
    
    # Identify critical blockers
    critical_blockers = []
    for activity in activities:
        if activity.status == ActivityStatus.BLOCKED and activity.priority == "critical":
            critical_blockers.append(f"{activity.name}: {activity.notes}")
    
    # Identify risk factors
    risk_factors = []
    query_status = status_data.get("query_status")
    safety_status = status_data.get("safety_status")
    monitoring_status = status_data.get("monitoring_status")
    
    if query_status and query_status.overdue_queries > 0:
        risk_factors.append(f"{query_status.overdue_queries} overdue data queries")
    
    if safety_status and safety_status.pending_events > 0:
        risk_factors.append(f"{safety_status.pending_events} pending safety events")
    
    if monitoring_status and monitoring_status.critical_findings > 0:
        risk_factors.append(f"{monitoring_status.critical_findings} sites with critical findings")
    
    # Calculate projected lock date
    max_days_remaining = max((activity.estimated_days_remaining for activity in activities), default=0)
    projected_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=max_days_remaining)
    projected_lock_date = projected_date.strftime("%Y-%m-%d")
    
    # Generate recommendations using LLM
    recommendations = generate_recommendations(activities, status_data)
    
    # Determine confidence level
    if overall_readiness >= 90 and len(critical_blockers) == 0:
        confidence_level = "high"
    elif overall_readiness >= 70 and len(critical_blockers) <= 2:
        confidence_level = "medium"
    else:
        confidence_level = "low"
    
    return ReadinessAssessment(
        overall_readiness_percentage=overall_readiness,
        projected_lock_date=projected_lock_date,
        critical_blockers=critical_blockers,
        risk_factors=risk_factors,
        recommendations=recommendations,
        confidence_level=confidence_level
    )


def generate_recommendations(activities: List[CloseoutActivity], status_data: Dict[str, Any]) -> List[str]:
    """Generate recommendations using LLM."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; generating basic recommendations")
        return [
            "Review all blocked activities and address critical issues",
            "Accelerate data query resolution process",
            "Complete pending safety event reconciliation",
            "Finalize remaining monitoring visits"
        ]
    
    # Prepare context for LLM
    context = {
        "activities": [
            {
                "name": activity.name,
                "category": activity.category.value,
                "status": activity.status.value,
                "completion_percentage": activity.completion_percentage,
                "estimated_days_remaining": activity.estimated_days_remaining,
                "priority": activity.priority
            } for activity in activities
        ],
        "query_status": status_data.get("query_status").__dict__ if status_data.get("query_status") else None,
        "safety_status": status_data.get("safety_status").__dict__ if status_data.get("safety_status") else None,
        "monitoring_status": status_data.get("monitoring_status").__dict__ if status_data.get("monitoring_status") else None
    }
    
    prompt = f"""
    You are a clinical trial database lock specialist. Based on the following closeout activities and status data, 
    provide specific, actionable recommendations to accelerate database lock readiness.
    
    Context: {json.dumps(context, indent=2)}
    
    Provide 5-7 specific recommendations in JSON format:
    {{
        "recommendations": [
            "Specific actionable recommendation 1",
            "Specific actionable recommendation 2",
            ...
        ]
    }}
    
    Focus on:
    1. Critical path activities
    2. Resource optimization
    3. Risk mitigation
    4. Process improvements
    5. Timeline acceleration
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
            return result.get("recommendations", [])
        
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
    
    return [
        "Prioritize resolution of critical data queries",
        "Accelerate safety event reconciliation process",
        "Complete outstanding monitoring visits",
        "Review and approve all pending activities"
    ]


def create_readiness_dashboard(assessment: ReadinessAssessment, activities: List[CloseoutActivity], 
                              status_data: Dict[str, Any], output_dir: str) -> str:
    """Create a comprehensive readiness dashboard."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Prepare dashboard data
    dashboard_data = {
        "readiness_assessment": {
            "overall_readiness_percentage": assessment.overall_readiness_percentage,
            "projected_lock_date": assessment.projected_lock_date,
            "confidence_level": assessment.confidence_level,
            "critical_blockers": assessment.critical_blockers,
            "risk_factors": assessment.risk_factors,
            "recommendations": assessment.recommendations
        },
        "activity_summary": {
            "total_activities": len(activities),
            "completed_activities": len([a for a in activities if a.status == ActivityStatus.COMPLETED]),
            "in_progress_activities": len([a for a in activities if a.status == ActivityStatus.IN_PROGRESS]),
            "blocked_activities": len([a for a in activities if a.status == ActivityStatus.BLOCKED]),
            "not_started_activities": len([a for a in activities if a.status == ActivityStatus.NOT_STARTED])
        },
        "category_breakdown": {},
        "activities": [
            {
                "activity_id": activity.activity_id,
                "name": activity.name,
                "category": activity.category.value,
                "status": activity.status.value,
                "completion_percentage": activity.completion_percentage,
                "estimated_days_remaining": activity.estimated_days_remaining,
                "priority": activity.priority,
                "assigned_to": activity.assigned_to,
                "last_updated": activity.last_updated,
                "notes": activity.notes
            } for activity in activities
        ],
        "status_details": {
            "query_status": status_data.get("query_status").__dict__ if status_data.get("query_status") else None,
            "safety_status": status_data.get("safety_status").__dict__ if status_data.get("safety_status") else None,
            "monitoring_status": status_data.get("monitoring_status").__dict__ if status_data.get("monitoring_status") else None
        },
        "generated_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    # Calculate category breakdown
    for category in ActivityCategory:
        category_activities = [a for a in activities if a.category == category]
        if category_activities:
            dashboard_data["category_breakdown"][category.value] = {
                "total": len(category_activities),
                "completed": len([a for a in category_activities if a.status == ActivityStatus.COMPLETED]),
                "avg_completion": sum(a.completion_percentage for a in category_activities) / len(category_activities),
                "total_days_remaining": sum(a.estimated_days_remaining for a in category_activities)
            }
    
    # Save dashboard
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    dashboard_file = os.path.join(output_dir, f"database_lock_readiness_dashboard_{timestamp}.json")
    
    with open(dashboard_file, "w") as f:
        json.dump(dashboard_data, f, indent=2)
    
    logger.info(f"Database lock readiness dashboard saved to {dashboard_file}")
    return dashboard_file


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

    parser = argparse.ArgumentParser(description="Database Lock Readiness Agent")
    parser.add_argument("activities_file", help="Path to closeout activities configuration file")
    parser.add_argument("--query_data", help="Path to data query status file")
    parser.add_argument("--safety_data", help="Path to safety event reconciliation file")
    parser.add_argument("--monitoring_data", help="Path to monitoring visit reports file")
    parser.add_argument("--output_dir", default="output", help="Directory for readiness dashboard output")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Load closeout activities
    activities = load_closeout_activities(args.activities_file)
    if not activities:
        logger.error("No closeout activities loaded")
        return

    # Analyze status data
    status_data = {}
    
    if args.query_data:
        status_data["query_status"] = analyze_query_status(args.query_data)
        logger.info(f"Query status: {status_data['query_status'].total_queries} total, {status_data['query_status'].open_queries} open")
    
    if args.safety_data:
        status_data["safety_status"] = analyze_safety_event_status(args.safety_data)
        logger.info(f"Safety status: {status_data['safety_status'].total_events} total, {status_data['safety_status'].pending_events} pending")
    
    if args.monitoring_data:
        status_data["monitoring_status"] = analyze_monitoring_visit_status(args.monitoring_data)
        logger.info(f"Monitoring status: {status_data['monitoring_status'].total_sites} sites, {status_data['monitoring_status'].completed_visits} completed")

    # Update activity status based on current data
    activities = update_activity_status(activities, status_data)

    # Calculate readiness assessment
    assessment = calculate_readiness_assessment(activities, status_data)

    # Create readiness dashboard
    dashboard_file = create_readiness_dashboard(assessment, activities, status_data, args.output_dir)

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    
    summary = f"Database lock readiness assessment completed: {assessment.overall_readiness_percentage:.1f}% ready, projected lock date: {assessment.projected_lock_date}"
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        summary
    )

    logger.info(f"Database lock readiness analysis complete: {assessment.overall_readiness_percentage:.1f}% ready")
    logger.info(f"Projected lock date: {assessment.projected_lock_date}")
    logger.info(f"Confidence level: {assessment.confidence_level}")


if __name__ == "__main__":
    main()