import os
import csv
import json
import logging
import datetime
from typing import Dict, List

from dotenv import load_dotenv
from litellm import completion
import yaml

from scripts.utils import setup_logging, get_llm_model_name

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

AGENT_ID = "1.300"


def _load_internal_db(path: str) -> Dict[str, Dict[str, float]]:
    """Load internal site performance metrics from a CSV."""
    data: Dict[str, Dict[str, float]] = {}
    if not os.path.exists(path):
        logger.error(f"Internal DB not found: {path}")
        return data
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                data[row["site_id"]] = {
                    "enrollment_rate": float(row.get("enrollment_rate", 0)),
                    "data_quality": float(row.get("data_quality", 0)),
                }
            except ValueError as exc:
                logger.warning(f"Invalid data in internal DB for site {row.get('site_id')}: {exc}")
    return data


def _load_public_db(path: str) -> Dict[str, str]:
    """Load public site database information mapping site_id to geography."""
    mapping: Dict[str, str] = {}
    if not os.path.exists(path):
        logger.error(f"Public DB not found: {path}")
        return mapping
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["site_id"]] = row.get("geography", "")
    return mapping


def _calculate_scores(internal: Dict[str, Dict[str, float]], public: Dict[str, str], counts: Dict[str, int]) -> List[Dict[str, object]]:
    """Calculate composite scores for each site."""
    results: List[Dict[str, object]] = []
    for site_id, metrics in internal.items():
        geography = public.get(site_id)
        if not geography:
            logger.debug(f"No geography for site {site_id}; skipping")
            continue
        patient_count = counts.get(geography, 0)
        base_score = 0.7 * metrics["enrollment_rate"] + 0.3 * metrics["data_quality"]
        composite = base_score * (patient_count or 1)
        results.append({
            "site_id": site_id,
            "geography": geography,
            "score": round(composite, 4),
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _generate_summary(ranked_sites: List[Dict[str, object]]) -> str:
    """Generate a short summary of the ranking using an LLM."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; skipping summary generation")
        return ""
    top = ranked_sites[:3]
    prompt = (
        "Provide a brief summary of the top clinical trial sites given the following data:\n"
        + json.dumps(top)
    )
    try:
        resp = completion(model=model_name, messages=[{"role": "user", "content": prompt}])
        return resp.choices[0].message.content
    except Exception as exc:
        logger.error(f"LLM call failed: {exc}")
        return ""


def generate_report(internal_db: str, public_db: str, population_report: str, output_dir: str) -> str:
    """Generate a ranked site report JSON."""
    internal = _load_internal_db(internal_db)
    public = _load_public_db(public_db)

    if not os.path.exists(population_report):
        logger.error(f"Population report not found: {population_report}")
        counts: Dict[str, int] = {}
    else:
        with open(population_report, "r") as f:
            try:
                data = json.load(f)
                counts = data.get("counts", {})
            except json.JSONDecodeError as exc:
                logger.error(f"Invalid population report JSON: {exc}")
                counts = {}

    ranked = _calculate_scores(internal, public, counts)
    summary = _generate_summary(ranked)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join(output_dir, "ranked_sites.json")
    with open(output_path, "w") as f:
        json.dump({"ranked_sites": ranked, "summary": summary}, f, indent=2)
    logger.info(f"Ranked site report saved to {output_path}")
    return output_path


def update_checklist(checklist_path: str, status: int) -> None:
    """Update the checklist.yml file for this agent."""
    with open(checklist_path, "r") as f:
        tasks = yaml.safe_load(f)

    for task in tasks:
        if task.get("agentId") == AGENT_ID:
            task["status"] = status
            break

    with open(checklist_path, "w") as f:
        yaml.safe_dump(tasks, f)


def write_progress_log(log_dir: str, status: int, summary: str) -> str:
    """Write a progress log JSON file."""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d%H%M%S")
    filename = f"{AGENT_ID}-{status}-{timestamp}.json"
    path = os.path.join(log_dir, filename)

    data = {
        "agentId": AGENT_ID,
        "status": status,
        "summary": summary,
        "timestamp": timestamp,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Progress log written to {path}")
    return path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Site Performance Evaluation Agent")
    parser.add_argument("internal_db", help="Path to internal site performance CSV")
    parser.add_argument("public_db", help="Path to public site database CSV")
    parser.add_argument("population_report", help="Path to patient population report JSON")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    parser.add_argument("--output_dir", default="output", help="Directory for output")
    args = parser.parse_args()

    generate_report(args.internal_db, args.public_db, args.population_report, args.output_dir)
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    write_progress_log(os.path.join("PROGRESS_LOGS", "new"), args.status, "Site performance evaluation completed")


if __name__ == "__main__":
    main()
