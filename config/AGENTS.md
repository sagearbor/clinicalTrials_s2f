AGENTS.MD: AI Agent Specifications
This document provides the detailed specifications for each AI agent in the workflow. It serves as the master blueprint for development. The content here is project-specific and should be modified for new projects.
Agent ID: 1.100 - Protocol Synopsis Generation Agent
Objective: To generate a structured, draft protocol synopsis from high-level study concepts.
Inputs: JSON object with therapeuticArea, productName, studyPhase, and primaryObjective.
Core Logic: Use an LLM with a structured prompt to expand inputs into standard synopsis sections (Rationale, Study Design, etc.), keeping the language general for any type of intervention.
Outputs: A DOCX file containing the formatted synopsis.
Completion Protocol:
Update config/checklist.yml for agentId: 1.100 to the new status percentage.
Write a new log file to PROGRESS_LOGS/new/ named 1.100-{status}-{timestamp}.json.
Agent ID: 1.200 - Patient Population Analysis Agent
Objective: To analyze data sources to quantify the addressable patient population for a given protocol.
Inputs: JSON object with detailed inclusionCriteria, exclusionCriteria, and geographies. Access to EHR/Claims data APIs.
Core Logic: Formulate queries based on criteria, execute against data source APIs, and aggregate anonymized patient counts.
Outputs: A JSON report with population counts and geographical heatmaps.
Completion Protocol:
Update config/checklist.yml for agentId: 1.200.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 1.300 - Site Performance Evaluation Agent
Objective: To rank potential sites based on historical performance and patient population alignment.
Inputs: Internal Database, Public Site Databases, Output from Agent 1.200.
Core Logic: Query databases for sites in patient hotspots, extract KPIs (enrollment rate, data quality), and calculate a composite score for ranking.
Outputs: A ranked list of potential sites in JSON or CSV format.
Completion Protocol:
Update checklist for agentId: 1.300.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 1.400 - Full Protocol Generation Agent
Objective: To expand the synopsis into a full, ICH E6-compliant clinical trial protocol.
Inputs: Approved Protocol Synopsis (from Agent 1.100), standard protocol templates, library of procedures.
Core Logic: Use an LLM to flesh out each section of the protocol template, inserting details from the synopsis and referencing the procedures library.
Outputs: A draft full clinical trial protocol in DOCX format.
Completion Protocol:
Update checklist for agentId: 1.400.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 2.100 - Essential Document Collection Agent
Objective: To manage the collection and perform initial QC on essential site documents.
Inputs: List of selected sites, essential document checklist, submitted documents (PDF, DOCX).
Core Logic: Track receipt of documents against the checklist. Use an LLM with vision to perform basic QC (e.g., check for signatures, dates). Flag missing or incomplete documents.
Outputs: A TMF document status dashboard (Web UI or report).
Completion Protocol:
Update checklist for agentId: 2.100.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 2.200 - Patient Recruitment Material Generator
Objective: To create targeted, IRB-compliant recruitment materials.
Inputs: Final protocol, patient population insights (from Agent 1.200).
Core Logic: Use an LLM to draft ad copy, flyers, and social media posts tailored to the target demographic, ensuring language is simple and meets regulatory guidelines.
Outputs: Draft recruitment materials in various formats (HTML, PNG, DOCX).
Completion Protocol:
Update checklist for agentId: 2.200.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 2.300 - Patient Pre-Screening & Engagement Agent
Objective: To interact with potential candidates via a chatbot to perform initial eligibility screening.
Inputs: Protocol I/E criteria, Chat Interface (Web, SMS).
Core Logic: Sequentially ask pre-defined screening questions. Use NLU to interpret responses. If a candidate passes, securely forward their contact info to the relevant site.
Outputs: JSON object with candidate details sent to a secure endpoint.
Completion Protocol:
Update checklist for agentId: 2.300.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 3.100 - Real-time Data Validation Agent
Objective: To run automated edit checks on incoming data from EDC systems.
Inputs: Live data feed from EDC, Data Validation Plan (edit check rules).
Core Logic: For each new piece of data submitted, run it against the set of validation rules (e.g., range checks, logical checks).
Outputs: Automated data queries created in the EDC system.
Completion Protocol:
Update checklist for agentId: 3.100.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 3.200 - Medical Coding Agent
Objective: To automatically suggest medical codes (e.g., MedDRA) for adverse events and medications.
Inputs: Uncoded text strings from the EDC (e.g., "headache").
Core Logic: Use an LLM fine-tuned on medical terminology or a dictionary-based mapping to find the most likely medical codes.
Outputs: Suggested codes with confidence scores for human review.
Completion Protocol:
Update checklist for agentId: 3.200.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 3.300 - Pharmacovigilance & Safety Event Alerting Agent
Objective: To monitor data streams for potential Serious Adverse Events (SAEs) or other safety signals.
Inputs: Live data from EDC, patient apps, call center logs.
Core Logic: Use a rules engine and keyword matching to identify potential safety events. When triggered, use an LLM to draft a narrative and send an immediate alert to the safety team.
Outputs: An alert payload (Email, SMS) and a draft event narrative.
Completion Protocol:
Update checklist for agentId: 3.300.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 3.400 - Site Monitoring Prioritization Agent
Objective: To analyze site data to identify risks and prioritize sites for monitoring visits.
Inputs: Data query rates, protocol deviation logs, Key Risk Indicators (KRIs).
Core Logic: Calculate a risk score for each site based on a weighted average of KRIs.
Outputs: A risk-based monitoring dashboard that ranks sites by risk score.
Completion Protocol:
Update checklist for agentId: 3.400.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 4.100 - Database Lock Readiness Agent
Objective: To track all activities required for database lock and predict a readiness date.
Inputs: Status of data queries, safety event reconciliation reports, final monitoring visit reports.
Core Logic: Aggregate the status of all close-out activities into a checklist.
Outputs: A readiness dashboard with a projected lock date.
Completion Protocol:
Update checklist for agentId: 4.100.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 4.200 - Statistical Analysis Plan (SAP) to Code Agent
Objective: To generate executable statistical code (Python/R) from the SAP document.
Inputs: SAP document (PDF, DOCX), locked dataset, standard code libraries.
Core Logic: Use an LLM to parse the SAP and translate the specified analyses into executable scripts for generating tables, listings, and figures (TLFs).
Outputs: Draft Python/R scripts.
Completion Protocol:
Update checklist for agentId: 4.200.
Write a new log file to PROGRESS_LOGS/new/.
Agent ID: 4.300 - Clinical Study Report (CSR) Generation Agent
Objective: To assemble a draft Clinical Study Report (CSR) compliant with ICH E3.
Inputs: Final protocol, generated TLFs, library of boilerplate text.
Core Logic: Use an LLM to assemble the CSR, populating sections with boilerplate text and inserting the generated tables and figures in the correct locations.
Outputs: A draft CSR in DOCX format.
Completion Protocol:
Update checklist for agentId: 4.300.
Write a new log file to PROGRESS_LOGS/new/.
