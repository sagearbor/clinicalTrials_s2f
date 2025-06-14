import os
import json
import logging
import datetime
from typing import Dict

from dotenv import load_dotenv
from litellm import completion
from docx import Document
from PIL import Image, ImageDraw, ImageFont
import yaml

from scripts.utils import setup_logging, get_llm_model_name

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

AGENT_ID = "2.200"


def generate_materials(protocol_path: str, insights_path: str, output_dir: str) -> Dict[str, str]:
    """Generate recruitment materials in DOCX, HTML, and PNG formats."""
    if not os.path.exists(protocol_path):
        logger.error(f"Protocol file not found: {protocol_path}")
        return {}
    if not os.path.exists(insights_path):
        logger.error(f"Insights file not found: {insights_path}")
        return {}

    model_name = get_llm_model_name()
    if not model_name:
        logger.error("LLM model configuration is missing.")
        return {}

    doc = Document(protocol_path)
    protocol_text = "\n".join(p.text for p in doc.paragraphs)

    with open(insights_path, "r") as f:
        insights = json.load(f)

    prompt = (
        "Using the following protocol information and patient population insights, "
        "draft IRB-compliant recruitment materials including ad copy, flyer text, "
        "and short social media posts. Use simple language.\n\n"
        f"Protocol Details:\n{protocol_text}\n\nPatient Insights:\n{json.dumps(insights)}"
    )

    try:
        logger.debug("Calling LLM for recruitment material generation")
        resp = completion(model=model_name, messages=[{"role": "user", "content": prompt}])
        material_text = resp.choices[0].message.content
    except Exception as exc:
        logger.error(f"LLM call failed: {exc}")
        return {}

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # DOCX output
    doc_out = Document()
    doc_out.add_heading("Recruitment Materials", level=1)
    for line in material_text.split("\n"):
        doc_out.add_paragraph(line)
    docx_path = os.path.join(output_dir, "recruitment_materials.docx")
    doc_out.save(docx_path)

    # HTML output
    html_content = "<html><body>" + "<br>".join(material_text.split("\n")) + "</body></html>"
    html_path = os.path.join(output_dir, "recruitment_materials.html")
    with open(html_path, "w") as f:
        f.write(html_content)

    # PNG output (simple text image)
    png_path = os.path.join(output_dir, "recruitment_materials.png")
    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    text_sample = material_text[:200] + ("..." if len(material_text) > 200 else "")
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((10, 10), text_sample, fill="black", font=font)
    img.save(png_path)

    logger.info(f"Materials saved to {output_dir}")
    return {"docx": docx_path, "html": html_path, "png": png_path}


def update_checklist(checklist_path: str, status: int) -> None:
    """Update the checklist.yml file for this agent."""
    with open(checklist_path, "r") as f:
        tasks = yaml.safe_load(f)

    for task in tasks:
        if task.get("agentId") == AGENT_ID:
            task["status"] = status
            break

    with open(checklist_path, "w") as f:
        yaml.safe_dump(tasks, f)


def write_progress_log(log_dir: str, status: int, summary: str) -> str:
    """Write a progress log JSON file."""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d%H%M%S")
    filename = f"{AGENT_ID}-{status}-{timestamp}.json"
    path = os.path.join(log_dir, filename)

    data = {
        "agentId": AGENT_ID,
        "status": status,
        "summary": summary,
        "timestamp": timestamp,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Progress log written to {path}")
    return path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Patient Recruitment Material Generator")
    parser.add_argument("protocol_docx", help="Path to the final protocol DOCX")
    parser.add_argument("insights_json", help="Path to patient insights JSON")
    parser.add_argument("--status", type=int, default=100, help="Completion status")
    parser.add_argument("--output_dir", default="output", help="Directory for generated materials")
    args = parser.parse_args()

    generate_materials(args.protocol_docx, args.insights_json, args.output_dir)
    update_checklist(os.path.join("config", "checklist.yml"), args.status)
    write_progress_log(os.path.join("PROGRESS_LOGS", "new"), args.status, "Recruitment materials generated")


if __name__ == "__main__":
    main()
