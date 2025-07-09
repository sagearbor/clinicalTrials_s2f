import os
import sys
import json
import yaml
import logging
from datetime import datetime, timezone
import frontmatter

# Add project root to the Python path to allow for local imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from scripts.utils import setup_logging

# --- Constants ---
LOGS_NEW_DIR = os.path.join('PROGRESS_LOGS', 'new')
LOGS_PROCESSED_DIR = os.path.join('PROGRESS_LOGS', 'processed')
ACTION_ITEMS_DIR = 'ACTION_ITEMS'
PROGRESS_MD_FILE = 'PROGRESS.md'
CHECKLIST_FILE = os.path.join('config', 'checklist.yml')

# --- Initial Setup ---
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

def check_for_blockers():
    """Scans the ACTION_ITEMS directory for any blocking issues."""
    if not os.path.exists(ACTION_ITEMS_DIR):
        return []
    blocking_issues = []
    for filename in os.listdir(ACTION_ITEMS_DIR):
        if filename.endswith('.md'):
            try:
                with open(os.path.join(ACTION_ITEMS_DIR, filename), 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)
                    if post.get('blocker') is True:
                        blocking_issues.append(filename)
            except Exception as e:
                logger.warning(f"Could not parse action item {filename}: {e}")
    return blocking_issues

def calculate_overall_progress():
    """Calculates overall progress based on the checklist."""
    if not os.path.exists(CHECKLIST_FILE):
        logger.error(f"Checklist file NOT found at {os.path.abspath(CHECKLIST_FILE)}")
        return 0.0, 0
        
    with open(CHECKLIST_FILE, 'r') as f:
        try:
            tasks = yaml.safe_load(f)
            if not tasks:
                logger.warning("Checklist file is empty or invalid.")
                return 0.0, 0
            
            total_progress = sum(task.get('status', 0) for task in tasks)
            overall_percentage = total_progress / len(tasks)
            logger.info(f"Progress Calculation: {overall_percentage:.1f}% ({len(tasks)} tasks)")
            return overall_percentage, len(tasks)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            return 0.0, 0

def main():
    """Reads logs, checks for blockers, and compiles a progress report."""
    logger.info("Starting progress update script...")
    
    blockers = check_for_blockers()

    if not os.path.exists(LOGS_NEW_DIR):
        os.makedirs(LOGS_NEW_DIR)
        logger.info(f"Created new logs directory at {LOGS_NEW_DIR}")

    log_files = [f for f in os.listdir(LOGS_NEW_DIR) if f.endswith('.json')]
    recent_updates = []
    log_files.sort()

    if not log_files:
        logger.info("No new progress logs to process.")
    else:
        logger.info(f"Found {len(log_files)} new log files to process.")

    for log_file in log_files:
        log_path_new = os.path.join(LOGS_NEW_DIR, log_file)
        try:
            with open(log_path_new, 'r') as f:
                log_data = json.load(f)
                update_line = (f"- **Agent {log_data.get('agentId', 'N/A')}**: {log_data.get('summary', 'No summary.')} "
                               f"*(Completed: {log_data.get('timestamp', 'N/A')})*")
                recent_updates.append(update_line)

            if not os.path.exists(LOGS_PROCESSED_DIR):
                os.makedirs(LOGS_PROCESSED_DIR)
            
            log_path_processed = os.path.join(LOGS_PROCESSED_DIR, log_file)
            os.rename(log_path_new, log_path_processed)
            logger.debug(f"Processed and moved {log_file}")
        except Exception as e:
            logger.error(f"Error processing log file {log_file}: {e}")
    
    overall_percentage, total_tasks = calculate_overall_progress()
    last_updated_time = datetime.now(timezone.utc).isoformat()

    # --- Generate Report Content ---
    report_content = f"""# Project Progress Report

*This report is auto-generated. Do not edit directly.*
*Run the "Update Progress Report" action to regenerate.*

*Last updated: {last_updated_time}*
"""

    if blockers:
        report_content += "\n---\n\n"
        report_content += "### ⚠️ **WORKFLOW BLOCKED** ⚠️\n\n"
        report_content += "**The system is halted. Resolve the following blocking issues found in the `/ACTION_ITEMS` directory:**\n"
        for issue in blockers:
            report_content += f"- `{issue}`\n"
        report_content += "\n---"

    report_content += f"""

## Overall Status

-   **Approximate Completion:** {overall_percentage:.1f}%
-   **Tasks Tracked:** {total_tasks}

---

## Recent Updates
"""
    if not recent_updates:
        report_content += "\n*(No new task completions logged since last update.)*"
    else:
        report_content += "\n" + "\n".join(recent_updates)
    
    with open(PROGRESS_MD_FILE, 'w') as f:
        f.write(report_content)

    logger.info(f"Successfully updated {PROGRESS_MD_FILE}.")

if __name__ == "__main__":
    main()
