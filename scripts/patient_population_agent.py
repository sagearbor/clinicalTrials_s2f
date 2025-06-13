import os
import sys
import json
import yaml
import requests
import datetime
from pathlib import Path

# Add project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Import from our custom utility scripts
from scripts.utils import get_llm_model_name
from litellm import completion

# --- MAIN AGENT LOGIC ---

def get_population_counts(input_data, api_url):
    """Makes a mock API call to get patient counts."""
    # In a real-world scenario, this would make an authenticated call
    # to a service like TriNetX or a real-world data provider.
    try:
        # We are mocking this with requests.post in the test
        response = requests.post(api_url, json=input_data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API call failed: {e}")
        return {}

def get_summary_from_llm(counts_data):
    """Uses an LLM to generate a human-readable summary of the counts."""
    model_name = get_llm_model_name()
    if not model_name:
        print("LLM model not configured. Skipping summary.")
        return ""

    prompt = f"Please provide a brief, one-sentence summary for the following patient population data: {json.dumps(counts_data)}"
    
    try:
        # We are mocking litellm.completion in the test
        response = completion(
            model=model_name,
            messages=[{"content": prompt, "role": "user"}]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM call failed: {e}")
        return ""

def generate_report(input_data, output_dir, api_url):
    """Generates a JSON report with patient counts and an AI-generated summary."""
    counts = get_population_counts(input_data, api_url)
    summary = get_summary_from_llm(counts)
    
    report_data = {
        "input_criteria": input_data,
        "counts": counts,
        "summary": summary # This line was previously missing
    }
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_path = os.path.join(output_dir, "patient_population_report.json")
    with open(output_path, 'w') as f:
        json.dump(report_data, f, indent=4)
        
    return output_path

# --- UTILITY FUNCTIONS FOR COMPLETION PROTOCOL ---

def update_checklist(checklist_path, new_status):
    """Updates the status of this agent in the master checklist."""
    with open(checklist_path, 'r') as f:
        checklist = yaml.safe_load(f)
    
    for task in checklist:
        if task['agentId'] == '1.200':
            task['status'] = new_status
            break
            
    with open(checklist_path, 'w') as f:
        yaml.safe_dump(checklist, f)

def write_progress_log(log_dir, status, summary):
    """Writes a JSON log file to the /new directory."""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # This is the corrected timestamp line using datetime.UTC
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d%H%M%S")
    log_file_name = f"1.200-{status}-{timestamp}.json"
    log_path = os.path.join(log_dir, log_file_name)
    
    log_data = {
        "agentId": "1.200",
        "timestamp": timestamp,
        "status": status,
        "summary": summary,
        "artifacts_created": [log_path] # Example artifact
    }
    
    with open(log_path, 'w') as f:
        json.dump(log_data, f, indent=4)
        
    return log_path

# Example of how to run this agent
if __name__ == '__main__':
    # This is an example run. In the real system, an orchestrator would call these functions.
    mock_input = {
        'inclusionCriteria': ['age > 60'],
        'exclusionCriteria': ['renal failure'],
        'geographies': ['US', 'EU']
    }
    generate_report(mock_input, "output", "http://mockapi.com/counts")
    update_checklist("config/checklist.yml", 100)
    write_progress_log("PROGRESS_LOGS/new", 100, "Patient population report generated.")

