Final Sanity Check
Use this checklist to ensure all repository components are correctly configured and work together as a cohesive system before starting development.

1. Core Repository Structure
[ ] Is there a config/ directory?

[ ] Is there a scripts/ directory?

[ ] Is there a .github/workflows/ directory?

[ ] Is there a PROGRESS_LOGS/ directory with new/ and processed/ subdirectories?

[ ] Is there an ACTION_ITEMS/ directory?

[ ] Is the LICENSE file absent (to ensure default copyright for a commercial project)?

2. Configuration Files (config/)
[ ] checklist.yml:

[ ] Do all agent name fields accurately and generically describe their function?

[ ] Do the dependencies for each task make logical sense?

[ ] Is the status for all tasks set to 0 initially?

[ ] agents.md:

[ ] Is the language generic (e.g., "product" instead of "drug")?

[ ] Does every agent have a clear "Completion Protocol" section?

[ ] Does the file contain a section for "Reporting Action Items"?

3. Automation Scripts (scripts/)
[ ] propose_next_tasks.py:

[ ] Does it correctly point to config/checklist.yml?

[ ] Does it check the /ACTION_ITEMS directory for blockers?

[ ] Does it write its output to NEXT_ACTIONS.md?

[ ] update_progress.py:

[ ] Does it read from PROGRESS_LOGS/new/ and move to PROGRESS_LOGS/processed/?

[ ] Does it check the /ACTION_ITEMS directory for blockers and include a warning in its report?

[ ] Does it write its output to PROGRESS.md?

[ ] check_action_items.py:

[ ] Does it read from the /ACTION_ITEMS directory?

[ ] Does it maintain a notification_log.json to avoid duplicate notifications?

[ ] Does it correctly set outputs (create_issue, issue_title, issue_body) for the GitHub Action?

4. GitHub Actions Workflows (.github/workflows/)
[ ] check_action_items.yml:

[ ] Does it correctly call scripts/check_action_items.py?

[ ] Does it have a second job (create-issue) that runs conditionally?

[ ] Does that job have the correct permissions: issues: write?

[ ] Does it have the correct usernames listed under assignees?

[ ] progress_updater.yml & task_proposer.yml:

[ ] Do they have a step to install dependencies from requirements.txt?

[ ] Do they have the permissions: contents: write block?

5. Root Files
[ ] README.md: Does it accurately reflect the final architecture (issue creation, action items, etc.)?

[ ] .gitignore: Does it correctly ignore .env files and __pycache__?

[ ] PROGRESS.md & NEXT_ACTIONS.md: Are they present as placeholder files, explaining that they are auto-generated?