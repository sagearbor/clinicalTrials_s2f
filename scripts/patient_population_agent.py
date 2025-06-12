import os
import json
import logging
from datetime import datetime
from typing import Dict

from dotenv import load_dotenv
from litellm import completion
import requests
import yaml

from scripts.utils import setup_logging, get_llm_model_name

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

AGENT_ID = "1.200"


def analyze_population(criteria: Dict[str, any], api_url: str) -> Dict[str, any]:
    """Query the patient database API and return counts."""
    try:
        logger.debug(f"Sending request to {api_url}")
        resp = requests.post(api_url, json=criteria, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error(f"API request failed: {exc}")
        return {}


def ask_llm(summary_prompt: str) -> str:
    """Call the LLM to generate a summary."""
    model = get_llm_model_name()
    if not model:
        logger.error("No LLM model configured.")
        return ""
    try:
        logger.debug("Calling LLM for summary generation")
        resp = completion(model=model, messages=[{"role": "user", "content": summary_prompt}])
        return resp.choices[0].message.content
    except Exception as exc:
        logger.error(f"LLM call failed: {exc}")
        return ""


def generate_report(input_data: Dict[str, any], output_dir: str, api_url: str) -> str:
    """Generate patient population report JSON."""
    counts = analyze_population(input_data, api_url)
    summary_prompt = f"Summarize patient counts: {json.dumps(counts)}"
    summary = ask_llm(summary_prompt)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    report = {
        "counts": counts,
        "summary": summary,
    }

    output_path = os.path.join(output_dir, "patient_population_report.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report written to {output_path}")
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

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
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

    parser = argparse.ArgumentParser(description="Patient Population Analysis Agent")
    parser.add_argument("input_json", help="Path to JSON file with patient criteria")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    parser.add_argument("--output_dir", default="output", help="Directory for output JSON")
    parser.add_argument("--api_url", default=os.getenv("PATIENT_API_URL", "http://example.com"), help="Patient data API URL")
    args = parser.parse_args()

    with open(args.input_json, "r") as f:
        input_data = json.load(f)

    generate_report(input_data, args.output_dir, args.api_url)
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    write_progress_log(os.path.join("PROGRESS_LOGS", "new"), args.status, "Patient population analyzed")


if __name__ == "__main__":
    main()
