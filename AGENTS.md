# AGENTS.MD: Global Project Standards

This document defines the mandatory, project-wide standards that all AI agents must follow when writing or modifying code in this repository. These instructions apply to all files unless overridden by a more specific `AGENTS.md` file in a subdirectory.

---

### **1. Environment and Configuration**

-   **Objective:** To ensure all scripts correctly load and use configuration from the `.env` file.
-   **Instructions:**
    1.  At the beginning of any executable Python script, import `from dotenv import load_dotenv`.
    2.  Immediately call `load_dotenv()` to load all environment variables.
    3.  Access all configuration variables using `os.getenv("VARIABLE_NAME")`.

---

### **2. Logging Standard**

-   **Objective:** To implement consistent, level-based logging across the application.
-   **Instructions:**
    1.  At the start of your main script file, import the `setup_logging` utility function: `from scripts.utils import setup_logging`.
    2.  Call `setup_logging()` immediately after loading the environment variables. This will configure the root logger for the entire application.
    3.  In any module, get a logger instance by using `logging.getLogger(__name__)`.
    4.  Use the different logging levels appropriately (`logging.debug()`, `logging.info()`, etc.).

    **Example Boilerplate for an Agent Script:**
    ```python
    import logging
    from dotenv import load_dotenv
    from scripts.utils import setup_logging

    # Load environment variables from .env file
    load_dotenv()

    # Configure logging for the application
    setup_logging()

    # Get a logger for the current module
    logger = logging.getLogger(__name__)

    logger.info("Agent script started.")
    ```

---

### **3. LLM Interaction**

-   **Objective:** To provide a standardized, flexible way to interact with Large Language Models.
-   **Instructions:**
    1.  All LLM calls **must** be made through the `litellm` library (`from litellm import completion`).
    2.  To get the correct model name string, import and call the utility function: `from scripts.utils import get_llm_model_name`.
    3.  Use the returned model string in your `litellm.completion()` call. This centralizes the logic for switching between providers like Azure, OpenAI, and Gemini.

    **Example of how an agent should make an LLM call:**
    ```python
    import logging
    from litellm import completion
    from scripts.utils import get_llm_model_name

    logger = logging.getLogger(__name__)

    def ask_llm(prompt_text):
        model_to_use = get_llm_model_name()
        if not model_to_use:
            logger.error("Could not determine LLM model to use. Check .env configuration.")
            return None

        try:
            logger.debug(f"Making LLM call with model: {model_to_use}")
            response = completion(
                model=model_to_use,
                messages=[{"content": prompt_text, "role": "user"}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    ```

---

### **4. Unit Testing Standard**

-   **Objective:** To ensure all agent logic is verifiable, robust, and self-contained.
-   **Instructions:**
    1.  **Framework:** All tests must be written using the `pytest` framework.
    2.  **File Naming:** For any script created, such as `scripts/my_agent.py`, a corresponding test file named `tests/test_my_agent.py` must also be created in a `/tests` directory.
    3.  **Test Creation:** Each function or major logical block within an agent's script must have at least one corresponding test case.
    4.  **Mocking External Services:**
        -   All external dependencies, especially LLM calls and API requests, **must be mocked**. Use the `pytest-mock` library (which provides the `mocker` fixture) for this purpose.
        -   Tests must not make actual network calls to any API (LLM, database, etc.).
    5.  **Mocking Data:**
        -   Tests must be self-contained. If a function reads from a file (e.g., `config/checklist.yml`), the test must create a temporary, mock version of that file for the test to read from. Do not rely on the actual project files being present.
        -   Use `tmp_path` fixture from `pytest` to create temporary files and directories for testing.

    **Example Test Structure (`tests/test_some_agent.py`):**
    ```python
    import pytest
    from scripts import some_agent # The script being tested

    def test_some_functionality_with_mock_data(mocker, tmp_path):
        # 1. Setup: Create mock input files using tmp_path
        mock_config_content = "key: value"
        mock_config_file = tmp_path / "mock_config.yml"
        mock_config_file.write_text(mock_config_content)

        # 2. Mocking: Mock the LLM call
        mock_llm_response = "This is a mock response from the LLM."
        mocker.patch('litellm.completion', return_value=mock_llm_response)

        # 3. Execution: Run the function being tested
        result = some_agent.process_data(config_path=mock_config_file)

        # 4. Assertion: Check if the result is as expected
        assert result is not None
        assert "mock response" in result
    ```
