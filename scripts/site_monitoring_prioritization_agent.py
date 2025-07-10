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

AGENT_ID = "3.400"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KRICategory(Enum):
    DATA_QUALITY = "data_quality"
    ENROLLMENT = "enrollment"
    PROTOCOL_COMPLIANCE = "protocol_compliance"
    SAFETY = "safety"
    OPERATIONAL = "operational"


@dataclass
class KeyRiskIndicator:
    """Represents a Key Risk Indicator (KRI)."""
    kri_id: str
    name: str
    description: str
    category: KRICategory
    weight: float
    threshold_low: float
    threshold_medium: float
    threshold_high: float
    unit: str
    direction: str  # higher_is_worse or lower_is_worse


@dataclass
class SiteData:
    """Represents site performance data."""
    site_id: str
    site_name: str
    principal_investigator: str
    country: str
    region: str
    enrollment_target: int
    enrollment_actual: int
    enrollment_rate: float
    data_query_rate: float
    protocol_deviations: int
    serious_ae_rate: float
    last_monitoring_visit: str
    days_since_last_visit: int
    data_quality_score: float
    source_data_verification_rate: float


@dataclass
class KRIScore:
    """Represents a KRI score for a site."""
    kri_id: str
    kri_name: str
    raw_value: float
    normalized_score: float
    risk_level: RiskLevel
    weight: float
    weighted_score: float
    threshold_exceeded: bool


@dataclass
class SiteRiskAssessment:
    """Represents a comprehensive risk assessment for a site."""
    site_id: str
    site_name: str
    overall_risk_score: float
    risk_level: RiskLevel
    kri_scores: List[KRIScore]
    priority_rank: int
    recommended_actions: List[str]
    next_visit_recommended: str
    visit_urgency: str
    assessment_timestamp: str


def load_kri_configuration(kri_config_file: str) -> List[KeyRiskIndicator]:
    """Load KRI configuration from file."""
    if not os.path.exists(kri_config_file):
        logger.error(f"KRI configuration file not found: {kri_config_file}")
        return []
    
    with open(kri_config_file, "r") as f:
        kri_data = json.load(f)
    
    kris = []
    for kri_item in kri_data.get("key_risk_indicators", []):
        kri = KeyRiskIndicator(
            kri_id=kri_item["kri_id"],
            name=kri_item["name"],
            description=kri_item["description"],
            category=KRICategory(kri_item["category"]),
            weight=kri_item.get("weight", 1.0),
            threshold_low=kri_item.get("threshold_low", 0.3),
            threshold_medium=kri_item.get("threshold_medium", 0.6),
            threshold_high=kri_item.get("threshold_high", 0.8),
            unit=kri_item.get("unit", ""),
            direction=kri_item.get("direction", "higher_is_worse")
        )
        kris.append(kri)
    
    logger.info(f"Loaded {len(kris)} KRI configurations")
    return kris


def parse_site_data(site_data_file: str) -> List[SiteData]:
    """Parse site performance data from file."""
    if not os.path.exists(site_data_file):
        logger.error(f"Site data file not found: {site_data_file}")
        return []
    
    with open(site_data_file, "r") as f:
        data = json.load(f)
    
    sites = []
    for site_item in data.get("sites", []):
        # Calculate days since last visit
        last_visit = site_item.get("last_monitoring_visit", "")
        days_since_last_visit = 0
        if last_visit:
            try:
                last_visit_date = datetime.datetime.fromisoformat(last_visit.replace('Z', '+00:00'))
                days_since_last_visit = (datetime.datetime.now(datetime.timezone.utc) - last_visit_date).days
            except ValueError:
                logger.warning(f"Invalid date format for site {site_item.get('site_id')}: {last_visit}")
        
        site = SiteData(
            site_id=site_item["site_id"],
            site_name=site_item.get("site_name", ""),
            principal_investigator=site_item.get("principal_investigator", ""),
            country=site_item.get("country", ""),
            region=site_item.get("region", ""),
            enrollment_target=site_item.get("enrollment_target", 0),
            enrollment_actual=site_item.get("enrollment_actual", 0),
            enrollment_rate=site_item.get("enrollment_rate", 0.0),
            data_query_rate=site_item.get("data_query_rate", 0.0),
            protocol_deviations=site_item.get("protocol_deviations", 0),
            serious_ae_rate=site_item.get("serious_ae_rate", 0.0),
            last_monitoring_visit=last_visit,
            days_since_last_visit=days_since_last_visit,
            data_quality_score=site_item.get("data_quality_score", 1.0),
            source_data_verification_rate=site_item.get("source_data_verification_rate", 1.0)
        )
        sites.append(site)
    
    logger.info(f"Parsed data for {len(sites)} sites")
    return sites


def calculate_kri_scores(site: SiteData, kris: List[KeyRiskIndicator]) -> List[KRIScore]:
    """Calculate KRI scores for a site."""
    kri_scores = []
    
    # Map site data to KRI values
    kri_value_map = {
        "enrollment_rate": site.enrollment_rate,
        "data_query_rate": site.data_query_rate,
        "protocol_deviation_rate": site.protocol_deviations / max(site.enrollment_actual, 1),
        "serious_ae_rate": site.serious_ae_rate,
        "days_since_last_visit": site.days_since_last_visit,
        "data_quality_score": site.data_quality_score,
        "source_data_verification_rate": site.source_data_verification_rate,
        "enrollment_percentage": (site.enrollment_actual / max(site.enrollment_target, 1)) * 100
    }
    
    for kri in kris:
        # Get raw value for this KRI
        raw_value = kri_value_map.get(kri.kri_id, 0.0)
        
        # Normalize score (0-1 scale)
        if kri.direction == "higher_is_worse":
            if raw_value <= kri.threshold_low:
                normalized_score = 0.0
                risk_level = RiskLevel.LOW
            elif raw_value <= kri.threshold_medium:
                normalized_score = 0.33
                risk_level = RiskLevel.MEDIUM
            elif raw_value <= kri.threshold_high:
                normalized_score = 0.66
                risk_level = RiskLevel.HIGH
            else:
                normalized_score = 1.0
                risk_level = RiskLevel.CRITICAL
        else:  # lower_is_worse
            if raw_value >= kri.threshold_high:
                normalized_score = 0.0
                risk_level = RiskLevel.LOW
            elif raw_value >= kri.threshold_medium:
                normalized_score = 0.33
                risk_level = RiskLevel.MEDIUM
            elif raw_value >= kri.threshold_low:
                normalized_score = 0.66
                risk_level = RiskLevel.HIGH
            else:
                normalized_score = 1.0
                risk_level = RiskLevel.CRITICAL
        
        # Calculate weighted score
        weighted_score = normalized_score * kri.weight
        
        # Check if threshold exceeded
        threshold_exceeded = (
            (kri.direction == "higher_is_worse" and raw_value > kri.threshold_medium) or
            (kri.direction == "lower_is_worse" and raw_value < kri.threshold_medium)
        )
        
        kri_score = KRIScore(
            kri_id=kri.kri_id,
            kri_name=kri.name,
            raw_value=raw_value,
            normalized_score=normalized_score,
            risk_level=risk_level,
            weight=kri.weight,
            weighted_score=weighted_score,
            threshold_exceeded=threshold_exceeded
        )
        kri_scores.append(kri_score)
    
    return kri_scores


def calculate_overall_risk_score(kri_scores: List[KRIScore]) -> float:
    """Calculate overall risk score from KRI scores."""
    if not kri_scores:
        return 0.0
    
    total_weighted_score = sum(score.weighted_score for score in kri_scores)
    total_weight = sum(score.weight for score in kri_scores)
    
    return total_weighted_score / total_weight if total_weight > 0 else 0.0


def determine_risk_level(overall_score: float) -> RiskLevel:
    """Determine risk level based on overall score."""
    if overall_score >= 0.75:
        return RiskLevel.CRITICAL
    elif overall_score >= 0.5:
        return RiskLevel.HIGH
    elif overall_score >= 0.25:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def generate_recommendations(site: SiteData, kri_scores: List[KRIScore], risk_level: RiskLevel) -> List[str]:
    """Generate monitoring recommendations using LLM."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; generating basic recommendations")
        return [
            "Schedule routine monitoring visit",
            "Review data quality metrics",
            "Assess protocol compliance",
            "Verify enrollment projections"
        ]
    
    # Prepare context for LLM
    context = {
        "site_info": {
            "site_id": site.site_id,
            "site_name": site.site_name,
            "country": site.country,
            "enrollment_target": site.enrollment_target,
            "enrollment_actual": site.enrollment_actual,
            "days_since_last_visit": site.days_since_last_visit
        },
        "risk_assessment": {
            "overall_risk_level": risk_level.value,
            "high_risk_kris": [
                {
                    "name": kri.kri_name,
                    "value": kri.raw_value,
                    "risk_level": kri.risk_level.value
                } for kri in kri_scores if kri.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            ]
        }
    }
    
    prompt = f"""
    You are a clinical trial monitoring specialist. Based on the site risk assessment data below, 
    provide specific, actionable recommendations for monitoring activities.
    
    Context: {json.dumps(context, indent=2)}
    
    Provide 3-5 specific recommendations in JSON format:
    {{
        "recommendations": [
            "Specific actionable recommendation 1",
            "Specific actionable recommendation 2",
            ...
        ]
    }}
    
    Focus on:
    1. Risk mitigation strategies
    2. Data quality improvements
    3. Protocol compliance enhancement
    4. Operational efficiency
    5. Timeline and resource optimization
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
    
    # Fallback recommendations based on risk level
    if risk_level == RiskLevel.CRITICAL:
        return [
            "Schedule immediate unscheduled monitoring visit",
            "Conduct comprehensive site assessment",
            "Review and retrain site staff",
            "Implement enhanced monitoring procedures"
        ]
    elif risk_level == RiskLevel.HIGH:
        return [
            "Schedule priority monitoring visit within 2 weeks",
            "Focus on data quality and protocol compliance",
            "Provide targeted site training",
            "Increase monitoring frequency"
        ]
    else:
        return [
            "Continue routine monitoring schedule",
            "Monitor KRI trends",
            "Provide preventive guidance",
            "Optimize visit efficiency"
        ]


def calculate_next_visit_date(risk_level: RiskLevel, days_since_last_visit: int) -> tuple[str, str]:
    """Calculate recommended next visit date and urgency."""
    base_date = datetime.datetime.now(datetime.timezone.utc)
    
    if risk_level == RiskLevel.CRITICAL:
        next_visit = base_date + datetime.timedelta(days=7)
        urgency = "immediate"
    elif risk_level == RiskLevel.HIGH:
        next_visit = base_date + datetime.timedelta(days=14)
        urgency = "urgent"
    elif risk_level == RiskLevel.MEDIUM:
        next_visit = base_date + datetime.timedelta(days=30)
        urgency = "priority"
    else:
        next_visit = base_date + datetime.timedelta(days=60)
        urgency = "routine"
    
    # Adjust based on time since last visit
    if days_since_last_visit > 90:
        next_visit = base_date + datetime.timedelta(days=14)
        urgency = "overdue"
    
    return next_visit.strftime("%Y-%m-%d"), urgency


def assess_site_risks(sites: List[SiteData], kris: List[KeyRiskIndicator]) -> List[SiteRiskAssessment]:
    """Assess risks for all sites and generate prioritized list."""
    assessments = []
    
    for site in sites:
        # Calculate KRI scores
        kri_scores = calculate_kri_scores(site, kris)
        
        # Calculate overall risk score
        overall_score = calculate_overall_risk_score(kri_scores)
        risk_level = determine_risk_level(overall_score)
        
        # Generate recommendations
        recommendations = generate_recommendations(site, kri_scores, risk_level)
        
        # Calculate next visit date
        next_visit_date, urgency = calculate_next_visit_date(risk_level, site.days_since_last_visit)
        
        assessment = SiteRiskAssessment(
            site_id=site.site_id,
            site_name=site.site_name,
            overall_risk_score=overall_score,
            risk_level=risk_level,
            kri_scores=kri_scores,
            priority_rank=0,  # Will be set after sorting
            recommended_actions=recommendations,
            next_visit_recommended=next_visit_date,
            visit_urgency=urgency,
            assessment_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        assessments.append(assessment)
    
    # Sort by risk score (highest first) and assign priority ranks
    assessments.sort(key=lambda x: x.overall_risk_score, reverse=True)
    for i, assessment in enumerate(assessments):
        assessment.priority_rank = i + 1
    
    logger.info(f"Completed risk assessment for {len(assessments)} sites")
    return assessments


def create_monitoring_dashboard(assessments: List[SiteRiskAssessment], kris: List[KeyRiskIndicator], 
                               output_dir: str) -> str:
    """Create a comprehensive monitoring prioritization dashboard."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Prepare dashboard data
    dashboard_data = {
        "dashboard_summary": {
            "total_sites": len(assessments),
            "critical_risk_sites": len([a for a in assessments if a.risk_level == RiskLevel.CRITICAL]),
            "high_risk_sites": len([a for a in assessments if a.risk_level == RiskLevel.HIGH]),
            "medium_risk_sites": len([a for a in assessments if a.risk_level == RiskLevel.MEDIUM]),
            "low_risk_sites": len([a for a in assessments if a.risk_level == RiskLevel.LOW]),
            "sites_requiring_immediate_visits": len([a for a in assessments if a.visit_urgency in ["immediate", "urgent"]]),
            "avg_risk_score": sum(a.overall_risk_score for a in assessments) / len(assessments) if assessments else 0,
            "dashboard_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        },
        "priority_ranking": [
            {
                "priority_rank": assessment.priority_rank,
                "site_id": assessment.site_id,
                "site_name": assessment.site_name,
                "overall_risk_score": assessment.overall_risk_score,
                "risk_level": assessment.risk_level.value,
                "next_visit_recommended": assessment.next_visit_recommended,
                "visit_urgency": assessment.visit_urgency,
                "top_risk_indicators": [
                    {
                        "kri_name": kri.kri_name,
                        "risk_level": kri.risk_level.value,
                        "raw_value": kri.raw_value
                    } for kri in sorted(assessment.kri_scores, key=lambda x: x.normalized_score, reverse=True)[:3]
                ],
                "recommended_actions": assessment.recommended_actions
            } for assessment in assessments
        ],
        "kri_analysis": {
            "kri_definitions": [
                {
                    "kri_id": kri.kri_id,
                    "name": kri.name,
                    "category": kri.category.value,
                    "weight": kri.weight,
                    "unit": kri.unit
                } for kri in kris
            ],
            "kri_performance": {}
        },
        "regional_analysis": {},
        "visit_scheduling": [
            {
                "site_id": assessment.site_id,
                "site_name": assessment.site_name,
                "next_visit_date": assessment.next_visit_recommended,
                "urgency": assessment.visit_urgency,
                "risk_level": assessment.risk_level.value
            } for assessment in sorted(assessments, key=lambda x: x.next_visit_recommended)
        ]
    }
    
    # Calculate KRI performance across all sites
    for kri in kris:
        kri_values = []
        for assessment in assessments:
            kri_score = next((score for score in assessment.kri_scores if score.kri_id == kri.kri_id), None)
            if kri_score:
                kri_values.append(kri_score.raw_value)
        
        if kri_values:
            dashboard_data["kri_analysis"]["kri_performance"][kri.kri_id] = {
                "name": kri.name,
                "avg_value": sum(kri_values) / len(kri_values),
                "min_value": min(kri_values),
                "max_value": max(kri_values),
                "sites_exceeding_threshold": len([v for v in kri_values if (
                    (kri.direction == "higher_is_worse" and v > kri.threshold_medium) or
                    (kri.direction == "lower_is_worse" and v < kri.threshold_medium)
                )])
            }
    
    # Save dashboard
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    dashboard_file = os.path.join(output_dir, f"monitoring_prioritization_dashboard_{timestamp}.json")
    
    with open(dashboard_file, "w") as f:
        json.dump(dashboard_data, f, indent=2)
    
    logger.info(f"Monitoring prioritization dashboard saved to {dashboard_file}")
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

    parser = argparse.ArgumentParser(description="Site Monitoring Prioritization Agent")
    parser.add_argument("kri_config", help="Path to KRI configuration file")
    parser.add_argument("site_data", help="Path to site performance data file")
    parser.add_argument("--output_dir", default="output", help="Directory for monitoring dashboard output")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Load KRI configuration
    kris = load_kri_configuration(args.kri_config)
    if not kris:
        logger.error("No KRI configurations loaded")
        return

    # Parse site data
    sites = parse_site_data(args.site_data)
    if not sites:
        logger.error("No site data loaded")
        return

    # Assess site risks
    assessments = assess_site_risks(sites, kris)

    # Create monitoring dashboard
    dashboard_file = create_monitoring_dashboard(assessments, kris, args.output_dir)

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    
    critical_sites = len([a for a in assessments if a.risk_level == RiskLevel.CRITICAL])
    high_risk_sites = len([a for a in assessments if a.risk_level == RiskLevel.HIGH])
    summary = f"Site monitoring prioritization completed: {len(assessments)} sites assessed, {critical_sites} critical risk, {high_risk_sites} high risk"
    
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        summary
    )

    logger.info(f"Site monitoring prioritization complete: {len(assessments)} sites ranked by risk")
    logger.info(f"Critical risk sites: {critical_sites}, High risk sites: {high_risk_sites}")


if __name__ == "__main__":
    main()