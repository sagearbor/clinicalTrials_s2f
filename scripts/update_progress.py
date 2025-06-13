import os
import json
import yaml # You will need to install PyYAML: pip install pyyaml
from datetime import datetime

LOGS_NEW_DIR = os.path.join('PROGRESS_LOGS', 'new')
LOGS_PROCESSED_DIR = os.path.join('PROGRESS_LOGS', 'processed')
PROGRESS_MD_FILE = 'PROGRESS.md'
CHECKLIST_FILE = os.path.join('config', 'checklist.yml')

def calculate_overall_progress():
    """Calculates overall progress based on the checklist."""
    if not os.path.exists(CHECKLIST_FILE):
        print(f"DEBUG: Checklist file NOT found at {os.path.abspath(CHECKLIST_FILE)}")
        return 0.0, 0
        
    with open(CHECKLIST_FILE, 'r') as f:
        try:
            tasks = yaml.safe_load(f)
            if not tasks:
                print("DEBUG: Checklist file is empty.")
                return 0.0, 0
            # Correctly calculate progress from the file
            total_progress = sum(task.get('status', 0) for task in tasks)
            overall_percentage = total_progress / len(tasks)
            print(f"DEBUG: Calculation complete. Percentage: {overall_percentage:.1f}%, Tasks: {len(tasks)}")
            return overall_percentage, len(tasks)
        except yaml.YAMLError as e:
            print(f"DEBUG: Error parsing YAML: {e}")
            return 0.0, 0

def main():
    """
    Reads new log files, compiles a progress report, and moves processed logs.
    """
    if not os.path.exists(LOGS_NEW_DIR):
        os.makedirs(LOGS_NEW_DIR)

    log_files = [f for f in os.listdir(LOGS_NEW_DIR) if f.endswith('.json')]
    recent_updates = []
    log_files.sort()
    for log_file in log_files:
        log_path_new = os.path.join(LOGS_NEW_DIR, log_file)
        try:
            with open(log_path_new, 'r') as f:
                log_data = json.load(f)
                update_line = (f"- **Agent {log_data['agentId']}**: {log_data['summary']} "
                               f"*(Completed: {log_data.get('timestamp', 'N/A')})*")
                recent_updates.append(update_line)

            if not os.path.exists(LOGS_PROCESSED_DIR):
                os.makedirs(LOGS_PROCESSED_DIR)
            log_path_processed = os.path.join(LOGS_PROCESSED_DIR, log_file)
            os.rename(log_path_new, log_path_processed)
        except Exception as e:
            print(f"Error processing log file {log_file}: {e}")
    
    overall_percentage, total_tasks = calculate_overall_progress()
    report_content = f"""# Project Progress Report

*This report is auto-generated. Do not edit directly.*
*Run the "Update Progress Report" action to regenerate.*

*Last updated: {datetime.now(datetime.UTC)().isoformat()}Z*

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

    print(f"Successfully updated {PROGRESS_MD_FILE}.")

if __name__ == "__main__":
    main()
