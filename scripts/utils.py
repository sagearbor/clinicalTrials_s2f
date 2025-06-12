import os
import logging

def get_llm_model_name():
    """
    Reads the LLM_PROVIDER from the environment and constructs the appropriate
    model name string for the 'litellm' library. This function centralizes
    the logic for model selection.

    Returns:
        str: A string formatted for use with litellm (e.g., "azure/deployment-name"),
             or None if the configuration is invalid.
    """
    provider = os.getenv("LLM_PROVIDER")
    model_name = ""

    if provider == "azure_openai":
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not deployment_name:
            logging.error("LLM_PROVIDER is 'azure_openai' but AZURE_OPENAI_DEPLOYMENT_NAME is not set.")
            return None
        model_name = f"azure/{deployment_name}"

    elif provider == "openai":
        # For standard OpenAI, litellm uses the model name directly.
        model_name = "gpt-4o-mini" # Or another model like gpt-4

    elif provider == "google_gemini":
        # For Gemini, litellm uses the model name with a "gemini/" prefix.
        model_name = "gemini/gemini-pro"

    elif provider == "anthropic":
        # For Anthropic, litellm uses the model name.
        model_name = "claude-3-haiku-20240307" # Example Haiku model

    else:
        logging.error(f"Unsupported or missing LLM_PROVIDER in .env file: '{provider}'")
        return None

    logging.info(f"Using LLM provider: {provider}, model string for litellm: '{model_name}'")
    return model_name

def setup_logging():
    """
    Sets up the global logging configuration based on the LOG_LEVEL
    environment variable.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logging.info(f"Logging level set to {log_level}")

