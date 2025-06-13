import os
import yaml # You will need to install PyYAML: pip install pyyaml

CHECKLIST_FILE = os.path.join('config', 'checklist.yml')
OUTPUT_FILE = 'NEXT_ACTIONS.md'

def get_tasks_from_checklist():
    """Parses the checklist.yml file to get the list of tasks."""
    if not os.path.exists(CHECKLIST_FILE):
        print(f"Error: Checklist file not found at {CHECKLIST_FILE}")
        return []
        
    with open(CHECKLIST_FILE, 'r') as f:
        try:
            # Correctly load data from the YAML file
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            return []

def generate_prompt(task):
    """Generates a detailed, copy-paste ready prompt for a given task."""
    agent_id = task['agentId']
    
    prompt = f"### Task: Execute Agent {agent_id} - {task['name']}\n\n"
    prompt += "**Objective:**\n"
    prompt += f"Your primary goal is to write the Python script and any other necessary artifacts to fulfill the objective for Agent {agent_id}. Refer to `config/agents.md` for the detailed business logic, inputs, and outputs.\n\n"
    prompt += "**Mandatory Project Standards:**\n"
    prompt += "While writing the code, you must adhere to all project-wide standards defined in the root `AGENTS.md` file, including:\n"
    prompt += "1.  **Configuration:** Use `dotenv` and `os.getenv`.\n"
    prompt += "2.  **Logging:** Implement level-based logging using the `setup_logging` utility.\n"
    prompt += "3.  **LLM Calls:** Use the `litellm` library via the `get_llm_model_name` utility.\n"
    prompt += "4.  **Unit Tests:** Create a corresponding test file in the `/tests` directory and mock all external calls.\n\n"
    prompt += "**CRITICAL - COMPLETION PROTOCOL:**\n"
    prompt += "After you have successfully created the agent's code and artifacts, you **must** perform the following two final actions to complete this task:\n"
    prompt += f"1.  **Update Checklist:** Modify `config/checklist.yml` to set the `status` for `agentId: {agent_id}` to `100` (or a partial percentage if not fully complete).\n"
    prompt += f"2.  **Write Log File:** Create a new JSON log file in the `PROGRESS_LOGS/new/` directory. The file should be named in the format `{agent_id}-<status>-<timestamp>.json` and contain a summary of the work completed."
    
    return prompt

def main():
    """Identifies available tasks and writes detailed prompts to an output file."""
    tasks = get_tasks_from_checklist()
    if not tasks:
        print("No tasks found in checklist. Aborting.")
        return

    task_status = {task['agentId']: task.get('status', 0) for task in tasks}
    
    available_tasks = []
    for task in tasks:
        if task.get('status', 0) == 100:
            continue
        dependencies_met = all(task_status.get(dep_id, 0) == 100 for dep_id in task.get('dependencies', []))
        if dependencies_met:
            available_tasks.append(task)
            
    available_tasks.sort(key=lambda x: (not x.get('critical_path', False), x['agentId']))
    
    content = "## Next Available Actions\n\n"
    content += "*This report is auto-generated. Run the 'Propose Next Actions' workflow to regenerate.*\n\n"
    
    if not available_tasks:
        content += "**No actions available. All tasks are either complete or waiting on dependencies.**"
    else:
        content += "Copy the full text for a task below and provide it to the AI agent (e.g., Codex).\n\n"
        content += "---\n\n"
        for task in available_tasks:
            path_marker = "CRITICAL PATH" if task.get('critical_path') else "Standard Task"
            content += f"### Task ID: `{task['agentId']}` ({path_marker})\n"
            content += "```markdown\n"
            content += generate_prompt(task)
            content += "\n```\n\n"
            content += "---\n\n"
            
    with open(OUTPUT_FILE, 'w') as f:
        f.write(content)
        
    print(f"Successfully updated {OUTPUT_FILE} with prompts for {len(available_tasks)} available actions.")

if __name__ == "__main__":
    main()
