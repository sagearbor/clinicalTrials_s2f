import os
import json
import logging
import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from dotenv import load_dotenv
from litellm import completion

from scripts.utils import setup_logging, get_llm_model_name

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

AGENT_ID = "2.300"


def load_screening_criteria(criteria_file: str) -> Dict[str, Any]:
    """Load protocol inclusion/exclusion criteria from JSON file."""
    if not os.path.exists(criteria_file):
        logger.error(f"Criteria file not found: {criteria_file}")
        return {}
    
    with open(criteria_file, "r") as f:
        return json.load(f)


def generate_screening_questions(criteria: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate screening questions based on I/E criteria using LLM."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.error("LLM model not configured")
        return []

    prompt = f"""
    Based on the following clinical trial inclusion and exclusion criteria, 
    generate a list of screening questions that can be asked to potential participants 
    via a chatbot interface. Each question should be clear, simple, and help determine 
    eligibility. Format the response as a JSON array of objects with 'question' and 'type' fields.
    
    Criteria: {json.dumps(criteria, indent=2)}
    
    Return format:
    [
        {{"question": "What is your age?", "type": "numeric"}},
        {{"question": "Do you have a history of diabetes?", "type": "boolean"}},
        {{"question": "Are you currently taking any medications?", "type": "text"}}
    ]
    """

    try:
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract JSON from response
        response_text = response.choices[0].message.content.strip()
        # Find JSON array in response
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            questions = json.loads(json_str)
            logger.info(f"Generated {len(questions)} screening questions")
            return questions
        else:
            logger.error("No valid JSON found in LLM response")
            return []
            
    except Exception as e:
        logger.error(f"Failed to generate screening questions: {e}")
        return []


def interpret_response(question: str, user_response: str, question_type: str) -> Dict[str, Any]:
    """Use NLU to interpret user responses and determine eligibility impact."""
    model_name = get_llm_model_name()
    if not model_name:
        logger.error("LLM model not configured")
        return {"interpreted_value": user_response, "eligibility_impact": "unknown"}

    prompt = f"""
    Analyze the following user response to a clinical trial screening question:
    
    Question: {question}
    Question Type: {question_type}
    User Response: {user_response}
    
    Interpret the response and determine:
    1. The standardized value (e.g., convert "yes"/"no" to boolean, extract numeric values)
    2. The eligibility impact (eligible/ineligible/needs_clarification)
    
    Return as JSON:
    {{
        "interpreted_value": "standardized value",
        "eligibility_impact": "eligible/ineligible/needs_clarification",
        "confidence": 0.95,
        "notes": "any additional notes"
    }}
    """

    try:
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.choices[0].message.content.strip()
        # Extract JSON from response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            interpretation = json.loads(json_str)
            return interpretation
        else:
            logger.error("No valid JSON found in interpretation response")
            return {"interpreted_value": user_response, "eligibility_impact": "unknown"}
            
    except Exception as e:
        logger.error(f"Failed to interpret response: {e}")
        return {"interpreted_value": user_response, "eligibility_impact": "unknown"}


def conduct_screening_session(questions: List[Dict[str, str]], responses: List[str]) -> Dict[str, Any]:
    """Conduct a screening session with provided responses."""
    if len(responses) != len(questions):
        logger.error(f"Mismatch between questions ({len(questions)}) and responses ({len(responses)})")
        return {"eligible": False, "reason": "Incomplete screening"}

    screening_results = []
    overall_eligibility = True
    ineligible_reasons = []

    for i, (question, response) in enumerate(zip(questions, responses)):
        interpretation = interpret_response(
            question["question"], 
            response, 
            question["type"]
        )
        
        result = {
            "question": question["question"],
            "response": response,
            "interpretation": interpretation
        }
        screening_results.append(result)
        
        if interpretation["eligibility_impact"] == "ineligible":
            overall_eligibility = False
            ineligible_reasons.append(f"Q{i+1}: {interpretation.get('notes', 'Screening criteria not met')}")

    return {
        "eligible": overall_eligibility,
        "screening_results": screening_results,
        "ineligible_reasons": ineligible_reasons,
        "session_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


def create_candidate_payload(screening_result: Dict[str, Any], contact_info: Dict[str, str]) -> Dict[str, Any]:
    """Create secure candidate payload for eligible candidates."""
    if not screening_result["eligible"]:
        logger.warning("Attempted to create payload for ineligible candidate")
        return {}

    payload = {
        "candidate_id": f"candidate_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "eligibility_status": "pre_screened_eligible",
        "contact_information": contact_info,
        "screening_summary": {
            "total_questions": len(screening_result["screening_results"]),
            "eligible": screening_result["eligible"],
            "session_timestamp": screening_result["session_timestamp"]
        },
        "next_steps": "Contact for full screening appointment",
        "data_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    return payload


def send_to_secure_endpoint(payload: Dict[str, Any], endpoint_url: str) -> bool:
    """Send candidate payload to secure endpoint (mock implementation)."""
    try:
        # In a real implementation, this would make an actual HTTP request
        # to a secure endpoint with proper authentication
        logger.info(f"Sending candidate payload to {endpoint_url}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Mock successful transmission
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payload to endpoint: {e}")
        return False


def save_screening_session(session_data: Dict[str, Any], output_dir: str) -> str:
    """Save screening session data to file."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"screening_session_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w") as f:
        json.dump(session_data, f, indent=2)
    
    logger.info(f"Screening session saved to {filepath}")
    return filepath


def update_checklist(checklist_path: str, status_val: int) -> None:
    """Update the checklist.yml file for this agent."""
    import yaml
    
    with open(checklist_path, "r") as f:
        tasks = yaml.safe_load(f)

    for task in tasks:
        if task.get("agentId") == AGENT_ID:
            task["status"] = status_val
            break

    with open(checklist_path, "w") as f:
        yaml.safe_dump(tasks, f)


def write_progress_log(log_dir: str, status_val: int, summary: str) -> str:
    """Write a progress log JSON file."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"{AGENT_ID}-{status_val}-{timestamp}.json"
    log_path = os.path.join(log_dir, filename)

    data = {
        "agentId": AGENT_ID,
        "status": status_val,
        "summary": summary,
        "timestamp": timestamp,
    }
    with open(log_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Progress log written to {log_path}")
    return log_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Patient Pre-Screening & Engagement Agent")
    parser.add_argument("criteria_file", help="Path to protocol I/E criteria JSON file")
    parser.add_argument("--responses", nargs="+", help="List of user responses for testing")
    parser.add_argument("--contact_name", help="Contact name for testing")
    parser.add_argument("--contact_email", help="Contact email for testing")
    parser.add_argument("--contact_phone", help="Contact phone for testing")
    parser.add_argument("--endpoint_url", default="https://example.com/secure/candidates", help="Secure endpoint URL")
    parser.add_argument("--output_dir", default="output", help="Directory for session output")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    args = parser.parse_args()

    # Load criteria and generate questions
    criteria = load_screening_criteria(args.criteria_file)
    if not criteria:
        logger.error("Failed to load screening criteria")
        return

    questions = generate_screening_questions(criteria)
    if not questions:
        logger.error("Failed to generate screening questions")
        return

    # If responses provided, conduct screening
    if args.responses:
        contact_info = {
            "name": args.contact_name or "Test User",
            "email": args.contact_email or "test@example.com",
            "phone": args.contact_phone or "555-0123"
        }
        
        screening_result = conduct_screening_session(questions, args.responses)
        session_data = {
            "questions": questions,
            "responses": args.responses,
            "screening_result": screening_result,
            "contact_info": contact_info
        }
        
        save_screening_session(session_data, args.output_dir)
        
        if screening_result["eligible"]:
            payload = create_candidate_payload(screening_result, contact_info)
            if payload:
                send_to_secure_endpoint(payload, args.endpoint_url)
                logger.info("Eligible candidate processed successfully")
        else:
            logger.info(f"Candidate ineligible: {screening_result.get('ineligible_reasons', [])}")
    else:
        # Just save the generated questions
        questions_file = os.path.join(args.output_dir, "screening_questions.json")
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        with open(questions_file, "w") as f:
            json.dump(questions, f, indent=2)
        logger.info(f"Generated screening questions saved to {questions_file}")

    # Update checklist and write progress log
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    write_progress_log(
        os.path.join("PROGRESS_LOGS", "new"), 
        args.status, 
        "Patient pre-screening agent implemented with NLU capabilities"
    )


if __name__ == "__main__":
    main()