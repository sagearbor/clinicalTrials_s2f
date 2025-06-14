import os
import sys
import json
import yaml
import logging
from datetime import datetime, timezone

# Add project root to the Python path to allow for local imports
# This is the CRITICAL fix for the ModuleNotFoundError
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from scripts.utils import setup_logging

# --- Constants ---
LOGS_NEW_DIR = os.path.join('PROGRESS_LOGS', 'new')
LOGS_PROCESSED_DIR = os.path.join('PROGRESS_LOGS', 'processed')
PROGRESS_MD_FILE = 'PROGRESS.md'
CHECKLIST_FILE = os.path.join('config', 'checklist.yml')

# --- Initial Setup ---
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

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
    """Reads new log files, compiles a progress report, and moves processed logs."""
    logger.info("Starting progress update script...")
    
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
    
    # This is the corrected datetime usage
    last_updated_time = datetime.now(timezone.utc).isoformat()

    report_content = f"""# Project Progress Report

*This report is auto-generated. Do not edit directly.*
*Run the "Update Progress Report" action to regenerate.*

*Last updated: {last_updated_time}*

---

## Overall Status

-   **Approximate Completion:** {overall_percentage:.1f}%
-   **Tasks Tracked:** {total_tasks}

---

## Recent Updates

"""
    if not recent_updates:
        report_content += "*(No new task completions logged since last update.)*"
    else:
        report_content += "\n".join(recent_updates)
    
    with open(PROGRESS_MD_FILE, 'w') as f:
        f.write(report_content)

    logger.info(f"Successfully updated {PROGRESS_MD_FILE}.")

if __name__ == "__main__":
    main()
