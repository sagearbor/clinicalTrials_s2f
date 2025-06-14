import os
import sys
import frontmatter

# --- Constants ---
ACTION_ITEMS_DIR = 'ACTION_ITEMS'

def main():
    """
    Checks for action items, determines the highest priority, and constructs
    a detailed email subject and body for the GitHub Action to use.
    """
    if not os.path.exists(ACTION_ITEMS_DIR):
        print("ACTION_ITEMS directory not found. Nothing to report.")
        # Set outputs to indicate no action is needed
        print("::set-output name=send_email::false")
        sys.exit(0)

    action_files = [f for f in os.listdir(ACTION_ITEMS_DIR) if f.endswith('.md')]

    if not action_files:
        print("No action items found.")
        print("::set-output name=send_email::false")
        sys.exit(0)

    print(f"Found {len(action_files)} action item(s). Parsing content...")

    # --- Process Files ---
    items_content = []
    is_blocker = False
    for filename in action_files:
        try:
            with open(os.path.join(ACTION_ITEMS_DIR, filename), 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
                if post.get('blocker') is True:
                    is_blocker = True
                
                # Format each item for the email body
                header = f"### 📄 {filename} (Priority: {post.get('priority', 'Normal')})"
                body = post.content
                items_content.append(f"{header}\n\n{body}\n\n---\n")
        except Exception as e:
            items_content.append(f"### 📄 {filename}\n\n**ERROR:** Could not parse file: {e}\n\n---\n")

    # --- Construct Email Subject and Body ---
    if is_blocker:
        subject = "[ACTION REQUIRED] CRITICAL BLOCKER in Agentic Workflow"
    else:
        subject = f"[ACTION REQUIRED] {len(action_files)} New Action Item(s) Logged"

    email_body = (
        "## Automated Alert: Human Intervention Required\n\n"
        "The following action items were logged by agents and require your review. "
        "After resolving an issue, please delete the corresponding markdown file from the `/ACTION_ITEMS` directory.\n\n"
        "---"
        "\n\n" + "\n".join(items_content)
    )

    # --- Set outputs for the GitHub Action ---
    # These lines are special commands that set variables for subsequent steps in the workflow.
    print("::set-output name=send_email::true")
    print(f"::set-output name=email_subject::{subject}")
    # We need to escape newlines for the multiline email body
    email_body_escaped = email_body.replace('%', '%25').replace('\n', '%0A').replace('\r', '%0D')
    print(f"::set-output name=email_body::{email_body_escaped}")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
