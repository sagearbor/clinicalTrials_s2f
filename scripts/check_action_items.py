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
    Checks for NEW action items that haven't been logged and sends a notification.
    """
    if not os.path.exists(ACTION_ITEMS_DIR):
        print("ACTION_ITEMS directory not found. Nothing to do.")
        sys.exit(0)

    # 1. Load state
    sent_files = load_sent_notifications()
    current_files = {f for f in os.listdir(ACTION_ITEMS_DIR) if f.endswith('.md')}
    
    # 2. Determine what's new
    new_items_to_notify = list(current_files - sent_files)

    if not new_items_to_notify:
        print("No new action items found to notify.")
        print("::set-output name=send_email::false")
        sys.exit(0)

    print(f"Found {len(new_items_to_notify)} new action item(s) to notify about.")

    # 3. Process only the new items for the email
    items_content = []
    is_blocker = False
    for filename in new_items_to_notify:
        try:
            with open(os.path.join(ACTION_ITEMS_DIR, filename), 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
                if post.get('blocker') is True:
                    is_blocker = True
                header = f"### 📄 {filename} (Priority: {post.get('priority', 'Normal')})"
                body = post.content
                items_content.append(f"{header}\n\n{body}\n\n---\n")
        except Exception as e:
            items_content.append(f"### 📄 {filename}\n\n**ERROR:** Could not parse file: {e}\n\n---\n")

    # 4. Construct email subject and body
    if is_blocker:
        subject = "[ACTION REQUIRED] CRITICAL BLOCKER in Agentic Workflow"
    else:
        subject = f"[ACTION REQUIRED] {len(new_items_to_notify)} New Action Item(s) Logged"

    email_body = (
        "## Automated Alert: Human Intervention Required\n\n"
        "The following new action items were logged by agents and require your review. "
        "After resolving an issue, please delete the corresponding markdown file from the `/ACTION_ITEMS` directory.\n\n"
        "---"
        "\n\n" + "\n".join(items_content)
    )

    # 5. Set outputs for the GitHub Action
    print("::set-output name=send_email::true")
    print(f"::set-output name=email_subject::{subject}")
    email_body_escaped = email_body.replace('%', '%25').replace('\n', '%0A').replace('\r', '%0D')
    print(f"::set-output name=email_body::{email_body_escaped}")
    
    # 6. CRITICAL FIX: Update the log with ALL current files
    update_sent_notifications(current_files)
    
    print("Email outputs set. Exiting successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
