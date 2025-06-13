## Next Available Actions

*This report is auto-generated. Run the 'Propose Next Actions' workflow to regenerate.*

Copy the full text for a task below and provide it to the AI agent (e.g., Codex).

---

### Task ID: `1.3` (CRITICAL PATH)
```markdown
### Task: Execute Agent 1.3 - Site Performance Evaluation Agent

**Objective:**
Your primary goal is to write the Python script and any other necessary artifacts to fulfill the objective for Agent 1.3. Refer to `config/agents.md` for the detailed business logic, inputs, and outputs.

**Mandatory Project Standards:**
While writing the code, you must adhere to all project-wide standards defined in the root `AGENTS.md` file, including:
1.  **Configuration:** Use `dotenv` and `os.getenv`.
2.  **Logging:** Implement level-based logging using the `setup_logging` utility.
3.  **LLM Calls:** Use the `litellm` library via the `get_llm_model_name` utility.
4.  **Unit Tests:** Create a corresponding test file in the `/tests` directory and mock all external calls.

**CRITICAL - COMPLETION PROTOCOL:**
After you have successfully created the agent's code and artifacts, you **must** perform the following two final actions to complete this task:
1.  **Update Checklist:** Modify `config/checklist.yml` to set the `status` for `agentId: 1.3` to `100` (or a partial percentage if not fully complete).
2.  **Write Log File:** Create a new JSON log file in the `PROGRESS_LOGS/new/` directory. The file should be named in the format `1.3-<status>-<timestamp>.json` and contain a summary of the work completed.
```

---

### Task ID: `2.2` (Standard Task)
```markdown
### Task: Execute Agent 2.2 - Patient Recruitment Material Generator

**Objective:**
Your primary goal is to write the Python script and any other necessary artifacts to fulfill the objective for Agent 2.2. Refer to `config/agents.md` for the detailed business logic, inputs, and outputs.

**Mandatory Project Standards:**
While writing the code, you must adhere to all project-wide standards defined in the root `AGENTS.md` file, including:
1.  **Configuration:** Use `dotenv` and `os.getenv`.
2.  **Logging:** Implement level-based logging using the `setup_logging` utility.
3.  **LLM Calls:** Use the `litellm` library via the `get_llm_model_name` utility.
4.  **Unit Tests:** Create a corresponding test file in the `/tests` directory and mock all external calls.

**CRITICAL - COMPLETION PROTOCOL:**
After you have successfully created the agent's code and artifacts, you **must** perform the following two final actions to complete this task:
1.  **Update Checklist:** Modify `config/checklist.yml` to set the `status` for `agentId: 2.2` to `100` (or a partial percentage if not fully complete).
2.  **Write Log File:** Create a new JSON log file in the `PROGRESS_LOGS/new/` directory. The file should be named in the format `2.2-<status>-<timestamp>.json` and contain a summary of the work completed.
```

---

