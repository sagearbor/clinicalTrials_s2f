import os
import yaml # You will need to install PyYAML: pip install pyyaml

CHECKLIST_FILE = os.path.join('config', 'checklist.yml')
OUTPUT_FILE = 'NEXT_ACTIONS.md'

def get_tasks_from_checklist():
    """
    Parses the checklist.yml file to get the list of tasks.
    """
    if not os.path.exists(CHECKLIST_FILE):
        print(f"Error: Checklist file not found at {CHECKLIST_FILE}")
        return []
        
    with open(CHECKLIST_FILE, 'r') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            return []

def main():
    """
    Identifies available tasks based on dependencies and writes them to an output file.
    """
    tasks = get_tasks_from_checklist()
    if not tasks:
        print("No tasks found in checklist. Aborting.")
        return

    task_status = {task['agentId']: task.get('status', 0) for task in tasks}
    
    available_tasks = []
    for task in tasks:
        # Skip if already complete
        if task.get('status', 0) == 100:
            continue

        # Check if all dependencies are met
        dependencies_met = True
        for dep_id in task.get('dependencies', []):
            if task_status.get(dep_id, 0) != 100:
                dependencies_met = False
                break
        
        if dependencies_met:
            available_tasks.append(task)
            
    # Sort by critical path first, then by agentId
    available_tasks.sort(key=lambda x: (not x.get('critical_path', False), x['agentId']))
    
    # Generate the output file content
    content = "## Next Available Actions\n\n"
    content += "*This report is auto-generated. Do not edit directly.*\n"
    content += "*Run the 'Propose Next Actions' workflow to regenerate.*\n\n"
    content += "The following tasks are available to be worked on in parallel. Their dependencies have been met.\n\n"
    
    if not available_tasks:
        content += "**No actions available. All tasks are either complete or waiting on dependencies.**"
    else:
        for task in available_tasks:
            path_marker = "CRITICAL PATH" if task.get('critical_path') else "Standard Task"
            content += f"- **Task ID:** `{task['agentId']}`\n"
            content += f"  - **Name:** {task['name']}\n"
            content += f"  - **Status:** {task.get('status', 0)}%\n"
            content += f"  - **Priority:** {path_marker}\n\n"
            
    with open(OUTPUT_FILE, 'w') as f:
        f.write(content)
        
    print(f"Successfully updated {OUTPUT_FILE} with {len(available_tasks)} available actions.")

if __name__ == "__main__":
    main()
