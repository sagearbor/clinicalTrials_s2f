import os
import sys
import json
import frontmatter
from datetime import datetime, timezone

# --- Constants ---
ACTION_ITEMS_DIR = 'ACTION_ITEMS'
NOTIFICATION_LOG_FILE = os.path.join(ACTION_ITEMS_DIR, 'notification_log.json')

def load_sent_notifications():
    """Loads the set of filenames that have already been notified."""
    if not os.path.exists(NOTIFICATION_LOG_FILE):
        return set()
    try:
        with open(NOTIFICATION_LOG_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('sent_files', []))
    except (json.JSONDecodeError, IOError):
        return set()

def update_sent_notifications(notified_files):
    """Updates the log with the set of all notified files."""
    try:
        with open(NOTIFICATION_LOG_FILE, 'w') as f:
            json.dump({'sent_files': list(notified_files)}, f, indent=2)
    except IOError as e:
        print(f"Error: Could not write to notification log: {e}")

def main():
    """
    Checks for NEW action items and constructs a title and body for a GitHub Issue.
    """
    github_output_file = os.getenv('GITHUB_OUTPUT')

    if not os.path.exists(ACTION_ITEMS_DIR):
        print("ACTION_ITEMS directory not found. Nothing to report.")
        if github_output_file:
            with open(github_output_file, 'a') as f:
                f.write("create_issue=false\n")
        sys.exit(0)

    sent_files = load_sent_notifications()
    current_files = {f for f in os.listdir(ACTION_ITEMS_DIR) if f.endswith('.md')}
    new_items_to_notify = list(current_files - sent_files)

    if not new_items_to_notify:
        print("No new action items found to create an issue for.")
        if github_output_file:
            with open(github_output_file, 'a') as f:
                f.write("create_issue=false\n")
        sys.exit(0)

    print(f"Found {len(new_items_to_notify)} new action item(s).")

    items_content = []
    is_blocker = False
    for filename in new_items_to_notify:
        try:
            with open(os.path.join(ACTION_ITEMS_DIR, filename), 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
                if post.get('blocker') is True:
                    is_blocker = True
                header = f"### 📄 `{filename}` (Priority: {post.get('priority', 'Normal')})"
                body = post.content
                items_content.append(f"{header}\n\n{body}\n\n---\n")
        except Exception as e:
            items_content.append(f"### 📄 `{filename}`\n\n**ERROR:** Could not parse file: {e}\n\n---\n")

    issue_title = "🔴 CRITICAL BLOCKER: Human Intervention Required" if is_blocker else f"🟡 Action Items Logged: {len(new_items_to_notify)} New Task(s)"
    
    issue_body = (
        "## Automated Alert: Human Intervention Required\n\n"
        "The following new action items were logged by agents and require your review. "
        "After resolving an issue, please **delete the corresponding markdown file** from the `/ACTION_ITEMS` directory and **close this issue**.\n\n"
        "---\n\n" + "\n".join(items_content)
    )

    if github_output_file:
        with open(github_output_file, 'a') as f:
            f.write("create_issue=true\n")
            f.write(f"issue_title={issue_title}\n")
            f.write("issue_body<<EOF\n")
            f.write(issue_body)
            f.write("\nEOF\n")
    
    update_sent_notifications(current_files)
    
    print("GitHub Issue outputs set. Exiting successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
