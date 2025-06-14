import os
import sys

ACTION_ITEMS_DIR = 'ACTION_ITEMS'

def main():
    """
    Checks if the ACTION_ITEMS directory exists and contains any files.
    Exits with a non-zero status code (failure) if items are found,
    which will trigger a GitHub Actions failure notification.
    """
    if not os.path.exists(ACTION_ITEMS_DIR):
        print("ACTION_ITEMS directory not found. Nothing to check. Exiting successfully.")
        sys.exit(0)

    action_items = [f for f in os.listdir(ACTION_ITEMS_DIR) if f.endswith('.md')]

    if not action_items:
        print("No action items found. Exiting successfully.")
        sys.exit(0)
    else:
        print(f"ERROR: Found {len(action_items)} action item(s) that require human attention:")
        for item in action_items:
            print(f"- {item}")
        print("\nExiting with status code 1 to trigger workflow failure notification.")
        sys.exit(1)

if __name__ == "__main__":
    main()
