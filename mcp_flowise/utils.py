"""
Utility functions for mcp_flowise, including logging setup, model filtering, and Flowise API interactions.

This module centralizes shared functionality such as:
1. Logging configuration for consistent log output across the application.
2. Safe redaction of sensitive data like API keys in logs.
3. Low-level interactions with the Flowise API for predictions and model management.
4. Flexible filtering of models based on whitelist/blacklist criteria.
"""

import os
import sys
import logging
import requests
import re
import json
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Flowise API configuration
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "")
FLOWISE_API_ENDPOINT = os.getenv("FLOWISE_API_ENDPOINT", "http://localhost:3000")


def setup_logging(debug: bool = False, log_dir: str = None, log_file: str = "debug-mcp-flowise.log") -> logging.Logger:
    """
    Sets up logging for the application, including outputting CRITICAL and ERROR logs to stdout.

    Args:
        debug (bool): If True, set log level to DEBUG; otherwise, INFO.
        log_dir (str): Directory where log files will be stored. Defaults to user's home directory.
        log_file (str): Name of the log file.

    Returns:
        logging.Logger: Configured logger instance.
    """
    if log_dir is None:
        log_dir = os.path.join(os.path.expanduser("~"), "mcp_logs")

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False  # Prevent log messages from propagating to the root logger

    # Remove all existing handlers to prevent accumulation
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    handlers = []

    # Attempt to create FileHandler
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(log_dir, log_file), mode="a")
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except Exception as e:
        # If FileHandler creation fails, print the error to stderr
        print(f"[ERROR] Failed to create log file handler: {e}", file=sys.stderr)

    # Attempt to create StreamHandler for ERROR level logs
    try:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        stdout_handler.setFormatter(formatter)
        handlers.append(stdout_handler)
    except Exception as e:
        # If StreamHandler creation fails, print the error to stderr
        print(f"[ERROR] Failed to create stdout log handler: {e}", file=sys.stderr)

    # Add all handlers to the logger
    for handler in handlers:
        logger.addHandler(handler)

    logger.info(f"Logging initialized. Writing logs to {os.path.join(log_dir, log_file)}")
    return logger


def redact_api_key(key: str) -> str:
    """
    Redacts the Flowise API key for safe logging output.

    Args:
        key (str): The API key to redact.

    Returns:
        str: The redacted API key or '<not set>' if the key is invalid.
    """
    if not key or len(key) <= 4:
        return "<not set>"
    return f"{key[:2]}{'*' * (len(key) - 4)}{key[-2:]}"


def normalize_tool_name(name: str) -> str:
    """
    Normalize tool names by converting to lowercase and replacing non-alphanumeric characters with underscores.

    Args:
        name (str): Original tool name.

    Returns:
        str: Normalized tool name. Returns 'unknown_tool' if the input is invalid.
    """
    logger = logging.getLogger(__name__)
    if not name or not isinstance(name, str):
        logger.warning("Invalid tool name input: %s. Using default 'unknown_tool'.", name)
        return "unknown_tool"
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", name).lower()
    logger.debug("Normalized tool name from '%s' to '%s'", name, normalized)
    return normalized or "unknown_tool"


def filter_models(model_list: list, model_type: str) -> list:
    """
    Filters models (chatflows or assistants) based on whitelist and blacklist criteria.
    Whitelist takes precedence over blacklist.

    Args:
        model_list (list): List of model dictionaries.
        model_type (str): Type of model ('chatflow' or 'assistant').

    Returns:
        list: Filtered list of models.
    """
    logger = logging.getLogger(__name__)

    # Define environment variable keys based on model_type
    if model_type == "chatflow":
        whitelist_ids = set(filter(bool, os.getenv("FLOWISE_WHITELIST_CHATFLOW_IDS", "").split(",")))
        blacklist_ids = set(filter(bool, os.getenv("FLOWISE_BLACKLIST_CHATFLOW_IDS", "").split(",")))
        whitelist_name_regex = os.getenv("FLOWISE_WHITELIST_CHATFLOW_NAME_REGEX", "")
        blacklist_name_regex = os.getenv("FLOWISE_BLACKLIST_CHATFLOW_NAME_REGEX", "")
    elif model_type == "assistant":
        whitelist_ids = set(filter(bool, os.getenv("FLOWISE_WHITELIST_ASSISTANT_IDS", "").split(",")))
        blacklist_ids = set(filter(bool, os.getenv("FLOWISE_BLACKLIST_ASSISTANT_IDS", "").split(",")))
        whitelist_name_regex = os.getenv("FLOWISE_WHITELIST_ASSISTANT_NAME_REGEX", "")
        blacklist_name_regex = os.getenv("FLOWISE_BLACKLIST_ASSISTANT_NAME_REGEX", "")
    else:
        logger.error(f"Unknown model type: {model_type}")
        return []

    filtered_models = []

    for model in model_list:
        model_id = model.get("id", "")
        model_name = model.get("name", "")

        is_whitelisted = False
        # Whitelist logic
        if whitelist_ids or whitelist_name_regex:
            if whitelist_ids and model_id in whitelist_ids:
                is_whitelisted = True
            if whitelist_name_regex and re.search(whitelist_name_regex, model_name, re.IGNORECASE):
                is_whitelisted = True

            if is_whitelisted:
                # Whitelisted => included, skip blacklist
                filtered_models.append(model)
                logger.debug(f"Including whitelisted {model_type} '{model_name}' (ID: '{model_id}').")
                continue
            else:
                # Not whitelisted => excluded
                logger.debug(f"Excluding non-whitelisted {model_type} '{model_name}' (ID: '{model_id}').")
                continue

        # If we didn't have a whitelist, apply the blacklist
        if blacklist_ids and model_id in blacklist_ids:
            logger.debug(f"Excluding {model_type} '{model_name}' (ID: '{model_id}') in blacklist.")
            continue
        if blacklist_name_regex and re.search(blacklist_name_regex, model_name, re.IGNORECASE):
            logger.debug(f"Excluding {model_type} '{model_name}' (ID: '{model_id}') matches blacklist regex.")
            continue

        # Passed all checks => included
        filtered_models.append(model)
        logger.debug(f"Including {model_type} '{model_name}' (ID: '{model_id}').")

    logger.info(f"Filtered {model_type}s: {len(filtered_models)} out of {len(model_list)}")
    return filtered_models


def fetch_models() -> dict:
    """
    Fetch a list of all chatflows and assistants from the Flowise API.

    Returns:
        dict: Dictionary containing 'chatflows' and 'assistants' lists.
              Each list contains dictionaries with 'id' and 'name'.
              Returns empty lists if there's an error.
    """
    logger = logging.getLogger(__name__)

    models = {
        "chatflows": [],
        "assistants": []
    }

    # Define endpoints based on model types
    endpoints = {
        "chatflows": "/api/v1/chatflows",
        "assistants": "/api/v1/assistants"
    }

    for model_type, endpoint_suffix in endpoints.items():
        url = f"{FLOWISE_API_ENDPOINT.rstrip('/')}{endpoint_suffix}"
        headers = {}
        if FLOWISE_API_KEY:
            headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"

        logger.debug(f"Fetching {model_type} from {url}")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            simplified_models = [{"id": m["id"], "name": m["name"]} for m in data]

            logger.debug(f"Fetched {model_type}: {simplified_models}")

            models[model_type] = simplified_models

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {model_type}: {e}")
            continue  # Proceed to next model_type

    return models


def filter_all_models(models: dict) -> dict:
    """
    Apply filtering to both chatflows and assistants.

    Args:
        models (dict): Dictionary containing 'chatflows' and 'assistants' lists.

    Returns:
        dict: Filtered models with 'chatflows' and 'assistants'.
    """
    logger = logging.getLogger(__name__)
    filtered = {}
    # Correctly map model categories to their singular model types
    for category, model_type in [('chatflows', 'chatflow'), ('assistants', 'assistant')]:
        filtered[category] = filter_models(models.get(category, []), model_type)
    return filtered


def fetch_and_filter_models() -> dict:
    """
    Fetch models from Flowise API and apply filtering.

    Returns:
        dict: Filtered models with 'chatflows' and 'assistants'.
    """
    models = fetch_models()
    filtered_models = filter_all_models(models)
    return filtered_models


def fetch_chatflows() -> dict:
    """
    Fetch and filter chatflows and assistants from the Flowise API.

    Returns:
        dict: Dictionary containing 'chatflows' and 'assistants' lists.
              Each list contains dictionaries with 'id' and 'name'.
              Returns empty lists if there's an error.
    """
    logger = logging.getLogger(__name__)
    try:
        filtered_models = fetch_and_filter_models()
        logger.debug(f"Filtered models: {filtered_models}")
        return filtered_models
    except Exception as e:
        logger.error(f"Error in fetch_chatflows: {e}")
        return {"chatflows": [], "assistants": []}


def flowise_predict(model_type: str, model_id: str, question: str) -> str:
    """
    Sends a question to a specific model (chatflow or assistant) via the Flowise API and returns the response text.

    Args:
        model_type (str): Type of model ('chatflow' or 'assistant').
        model_id (str): The ID of the Flowise model to be used.
        question (str): The question or prompt to send to the model.

    Returns:
        str: The response text from the Flowise API or an error string if something went wrong.
    """
    logger = logging.getLogger(__name__)

    # Determine endpoint based on model type
    if model_type == "chatflow":
        endpoint_suffix = "/api/v1/prediction/"
    elif model_type == "assistant":
        endpoint_suffix = "/api/v1/prediction/assistant/"
    else:
        logger.error(f"Invalid model_type: {model_type}")
        return f"Error: Invalid model_type '{model_type}'"

    # Construct the Flowise API URL for predictions
    url = f"{FLOWISE_API_ENDPOINT.rstrip('/')}{endpoint_suffix}{model_id}"
    headers = {
        "Content-Type": "application/json",
    }
    if FLOWISE_API_KEY:
        headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"

    payload = {
        "modelId": model_id,  # Adjust key if different for assistants
        "question": question,
        "streaming": False
    }
    logger.debug(f"Sending prediction request to {url} with payload: {payload}")

    try:
        # Send POST request to the Flowise API
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        logger.debug(f"Prediction response (HTTP {response.status_code}): {response.text}")
        return response.text
    except requests.exceptions.RequestException as e:
        # Log and return the error as a string
        logger.error(f"Error during prediction: {e}")
        return f"Error: {str(e)}"
