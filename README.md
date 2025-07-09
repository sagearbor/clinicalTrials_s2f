# Agentic AI for Clinical Trial Automation

## Overview

This project is an end-to-end, modular AI agentic solution designed to dramatically accelerate and improve the efficiency of clinical trials. By breaking down the complex lifecycle of a trial into discrete, automated tasks, this system aims to reduce timelines, lower costs, and minimize human error from study design to final reporting.

The system is built as a collection of specialized AI agents that are orchestrated by a workflow engine defined in this repository.

## Project Architecture

This repository is designed as a reusable framework for agentic workflows. The core logic is separated from the project-specific configuration.

-   **`/scripts`**: Contains the generic Python "engine" for the workflow, including the scripts for proposing tasks and updating progress.
-   **`/config`**: Contains the project-specific definitions, including the list of tasks (`checklist.yml`) and the detailed agent specifications (`agents.md`).
-   **`/PROGRESS_LOGS`**: A directory where each agent records its work by writing a unique JSON log file upon task completion. This creates an auditable trail and prevents conflicts.
-   **`/ACTION_ITEMS`**: An "inbox" for issues discovered by agents that require human intervention. When a new file appears here, a GitHub Action automatically creates a new Issue in the repository.
-   **`.github/workflows`**: Contains GitHub Actions that automate the workflow, allowing you to update reports, propose next tasks, and create notification issues.

## Correct Directory Structure

Use the following structure as a guide to ensure all files are in their correct locations.


/ (your root project folder)
├── .github/
│   └── workflows/
│       ├── check_action_items.yml
│       ├── progress_updater.yml
│       └── task_proposer.yml
├── config/
│   ├── agents.md
│   └── checklist.yml
├── scripts/
│   ├── check_action_items.py
│   ├── propose_next_tasks.py
│   └── update_progress.py
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── NEXT_ACTIONS.md
├── PROGRESS.md
└── README.md


## Key Files

-   **[config/agents.md](config/agents.md):** The master design document. It contains detailed specifications for each AI agent.
-   **[config/checklist.yml](config/checklist.yml):** The granular task list and state tracker for the entire project.
-   **[PROGRESS.md](PROGRESS.md):** An auto-generated report summarizing the project's status and any blocking action items.
-   **[NEXT_ACTIONS.md](NEXT_ACTIONS.md):** An auto-generated file that lists the next set of tasks that are ready to be worked on in parallel, or indicates if the workflow is blocked.

## Getting Started

### Prerequisites

-   Python 3.9+
-   An LLM API Key (e.g., OpenAI, Google Gemini)

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone [your-repository-url]
    cd [repository-name]
    ```

2.  **Set up environment variables:**
    Copy the example environment file and fill in your credentials. This file is ignored by Git.
    ```bash
    cp .env.example .env
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Workflow:**
    -   Navigate to the "Actions" tab in your GitHub repository.
    -   Run the "Propose Next Actions" workflow to generate the `NEXT_ACTIONS.md` file.
    -   Begin development on the proposed tasks.
    -   After agents have run and produced logs, run the "Update Progress Report" workflow to update `PROGRESS.md`.
    -   The "Check for Action Items" workflow will run automatically on a schedule to notify you of any issues.
