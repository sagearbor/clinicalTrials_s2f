import os
import json
import logging
import datetime
from typing import List, Dict, Any
from pathlib import Path

from dotenv import load_dotenv
from litellm import completion
import yaml

from scripts.utils import setup_logging, get_llm_model_name

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

AGENT_ID = "2.100"


def _load_file(path: str) -> Any:
    """Load YAML or JSON file."""
    if not os.path.exists(path):
        logger.error(f"File not found: {path}")
        return None
    with open(path, "r") as f:
        if path.endswith((".yml", ".yaml")):
            return yaml.safe_load(f)
        return json.load(f)


def qc_document(doc_path: str) -> bool:
    """Use an LLM to check if a document contains a signature and date."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.warning("LLM model not configured; skipping QC")
        return False

    try:
        with open(doc_path, "rb") as f:
            content = f.read(2000)
        prompt = (
            "Does the following document text include a signature and a date? "
            "Respond with 'PASS' or 'FAIL'.\n" + str(content)
        )
        resp = completion(model=model_name, messages=[{"role": "user", "content": prompt}])
        result = resp.choices[0].message.content.strip().lower()
        return "pass" in result
    except Exception as exc:
        logger.error(f"QC failed for {doc_path}: {exc}")
        return False


def generate_dashboard(site_list_file: str, checklist_file: str, submissions_dir: str, output_dir: str) -> str:
    """Generate a document status dashboard JSON."""
    sites: List[str] = _load_file(site_list_file) or []
    checklist: List[str] = _load_file(checklist_file) or []

    status: Dict[str, Dict[str, Dict[str, bool]]] = {}
    for site in sites:
        site_status: Dict[str, Dict[str, bool]] = {}
        for doc in checklist:
            received = False
            doc_path = ""
            for ext in ["pdf", "docx"]:
                candidate = os.path.join(submissions_dir, site, f"{doc}.{ext}")
                if os.path.exists(candidate):
                    received = True
                    doc_path = candidate
                    break
            passed_qc = qc_document(doc_path) if received else False
            site_status[doc] = {"received": received, "passed_qc": passed_qc}
        status[site] = site_status

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = os.path.join(output_dir, "document_status.json")
    with open(out_path, "w") as f:
        json.dump(status, f, indent=2)
    logger.info(f"Dashboard saved to {out_path}")
    return out_path


def update_checklist(checklist_path: str, status_val: int) -> None:
    """Update the checklist.yml file for this agent."""
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
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d%H%M%S")
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

    parser = argparse.ArgumentParser(description="Essential Document Collection Agent")
    parser.add_argument("site_list", help="Path to file listing selected sites")
    parser.add_argument("doc_checklist", help="Path to essential document checklist file")
    parser.add_argument("submissions_dir", help="Directory containing submitted documents")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    parser.add_argument("--output_dir", default="output", help="Directory for dashboard output")
    args = parser.parse_args()

    generate_dashboard(args.site_list, args.doc_checklist, args.submissions_dir, args.output_dir)
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    write_progress_log(os.path.join("PROGRESS_LOGS", "new"), args.status, "Essential documents processed")


if __name__ == "__main__":
    main()
