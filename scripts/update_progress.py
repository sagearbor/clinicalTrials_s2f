import os
import json
from datetime import datetime

LOGS_NEW_DIR = 'PROGRESS_LOGS/new'
LOGS_PROCESSED_DIR = 'PROGRESS_LOGS/processed'
PROGRESS_MD_FILE = 'PROGRESS.md'
CHECKLIST_FILE = 'config/checklist.yml'

def calculate_overall_progress():
    """Calculates overall progress based on the checklist."""
    # This is a placeholder for YAML parsing. Use a library like PyYAML in a real implementation.
    # For this example, we'll simulate reading it.
    # with open(CHECKLIST_FILE, 'r') as f:
    #     tasks = yaml.safe_load(f)
    # total_progress = sum(task['status'] for task in tasks)
    # overall_percentage = total_progress / len(tasks)
    # return overall_percentage, len(tasks)
    # In a real scenario, you'd parse the YAML file. Here we just return dummy data.
    return 50.0, 14 # Dummy data

def main():
    """
    Reads new log files, compiles a progress report, and moves processed logs.
    """
    if not os.path.exists(LOGS_NEW_DIR):
        print(f"Directory not found: {LOGS_NEW_DIR}")
        return

    log_files = [f for f in os.listdir(LOGS_NEW_DIR) if f.endswith('.json')]
    if not log_files:
        print("No new progress logs to process.")
        return

    # Sort files by name, which should correspond to timestamp
    log_files.sort()
    
    recent_updates = []
    for log_file in log_files:
        log_path_new = os.path.join(LOGS_NEW_DIR, log_file)
        try:
            with open(log_path_new, 'r') as f:
                log_data = json.load(f)
                update_line = (f"- **Agent {log_data['agentId']}**: {log_data['summary']} "
                               f"*(Completed: {log_data['timestamp']})*")
                recent_updates.append(update_line)

            # Move processed file
            if not os.path.exists(LOGS_PROCESSED_DIR):
                os.makedirs(LOGS_PROCESSED_DIR)
            log_path_processed = os.path.join(LOGS_PROCESSED_DIR, log_file)
            os.rename(log_path_new, log_path_processed)

        except Exception as e:
            print(f"Error processing log file {log_file}: {e}")

    # Generate the new PROGRESS.md content
    overall_percentage, total_tasks = calculate_overall_progress()
    report_content = f"""# Project Progress Report

*Last updated: {datetime.utcnow().isoformat()}Z*

---

## Overall Status

-   **Approximate Completion:** {overall_percentage:.1f}%
-   **Tasks Tracked:** {total_tasks}

---

## Recent Updates

"""
    report_content += "\n".join(recent_updates)
    
    with open(PROGRESS_MD_FILE, 'w') as f:
        f.write(report_content)

    print(f"Successfully updated {PROGRESS_MD_FILE} with {len(log_files)} new updates.")

if __name__ == "__main__":
    main()
