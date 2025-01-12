"""
Utility functions for mcp_flowise, including logging setup, chatflow filtering, and Flowise API interactions.

This module centralizes shared functionality such as:
1. Logging configuration for consistent log output across the application.
2. Safe redaction of sensitive data like API keys in logs.
3. Low-level interactions with the Flowise API for predictions and chatflow management.
4. Flexible filtering of chatflows based on whitelist/blacklist criteria.
"""

import os
import sys
import logging
import requests
import re
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Flowise API configuration
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "")
FLOWISE_API_ENDPOINT = os.getenv("FLOWISE_API_ENDPOINT", "http://localhost:3000")

# Filtering environment variables
WHITELIST_IDS = set(filter(bool, os.getenv("FLOWISE_WHITELIST_ID", "").split(",")))
BLACKLIST_IDS = set(filter(bool, os.getenv("FLOWISE_BLACKLIST_ID", "").split(",")))
WHITELIST_NAME_REGEX = os.getenv("FLOWISE_WHITELIST_NAME_REGEX", "")
BLACKLIST_NAME_REGEX = os.getenv("FLOWISE_BLACKLIST_NAME_REGEX", "")

def setup_logging(debug: bool = False, log_dir: str = "logs", log_file: str = "debug-mcp-flowise.log") -> logging.Logger:
    """
    Sets up logging for the application, including outputting CRITICAL and ERROR logs to stdout.

    Args:
        debug (bool): If True, set log level to DEBUG; otherwise, INFO.
        log_dir (str): Directory where log files will be stored.
        log_file (str): Name of the log file.

    Returns:
        logging.Logger: Configured logger instance.
    """
    log_path = os.path.join(log_dir, log_file)

    # Create handlers list
    handlers = []

    # Attempt to create FileHandler
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode="a")
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except Exception as e:
        print(f"Failed to create log file handler: {e}", file=sys.stderr)

    # Attempt to create StreamHandler
    try:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        stdout_handler.setFormatter(formatter)
        handlers.append(stdout_handler)
    except Exception as e:
        print(f"Failed to create stdout log handler: {e}", file=sys.stderr)

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="[%(levelname)s] %(asctime)s - %(message)s",
        handlers=handlers,
    )

    # Obtain the logger after configuration
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized. Writing logs to %s", log_path)
    return logger

# Set up logging before obtaining the logger
DEBUG = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
setup_logging(debug=DEBUG)

# Obtain the logger after setup_logging
logger = logging.getLogger(__name__)

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
    if not name or not isinstance(name, str):
        logger.warning("Invalid tool name input: %s. Using default 'unknown_tool'.", name)
        return "unknown_tool"
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", name).lower()
    logger.debug("Normalized tool name from '%s' to '%s'", name, normalized)
    return normalized or "unknown_tool"

def filter_chatflows(chatflows: list[dict]) -> list[dict]:
    """
    Filters chatflows based on whitelist and blacklist criteria.
    Whitelist takes precedence over blacklist.

    Args:
        chatflows (list[dict]): A list of chatflow dictionaries.

    Returns:
        list[dict]: Filtered list of chatflows.
    """
    filtered_chatflows = []

    for chatflow in chatflows:
        chatflow_id = chatflow.get("id", "")
        chatflow_name = chatflow.get("name", "")

        # Flags to determine inclusion
        is_whitelisted = False

        # Check Whitelist
        if WHITELIST_IDS or WHITELIST_NAME_REGEX:
            if WHITELIST_IDS and chatflow_id in WHITELIST_IDS:
                is_whitelisted = True
            if WHITELIST_NAME_REGEX and re.search(WHITELIST_NAME_REGEX, chatflow_name):
                is_whitelisted = True

            if not is_whitelisted:
                # If not whitelisted, apply blacklist
                if BLACKLIST_IDS and chatflow_id in BLACKLIST_IDS:
                    logger.debug("Skipping chatflow '%s' (ID: '%s') - In blacklist.", chatflow_name, chatflow_id)
                    continue  # Exclude blacklisted by ID
                if BLACKLIST_NAME_REGEX and re.search(BLACKLIST_NAME_REGEX, chatflow_name):
                    logger.debug("Skipping chatflow '%s' (ID: '%s') - Name matches blacklist regex.", chatflow_name, chatflow_id)
                    continue  # Exclude blacklisted by name
        else:
            # If no whitelist, apply blacklist directly
            if BLACKLIST_IDS and chatflow_id in BLACKLIST_IDS:
                logger.debug("Skipping chatflow '%s' (ID: '%s') - In blacklist.", chatflow_name, chatflow_id)
                continue  # Exclude blacklisted by ID
            if BLACKLIST_NAME_REGEX and re.search(BLACKLIST_NAME_REGEX, chatflow_name):
                logger.debug("Skipping chatflow '%s' (ID: '%s') - Name matches blacklist regex.", chatflow_name, chatflow_id)
                continue  # Exclude blacklisted by name

        # Include the chatflow if it passes all filters
        filtered_chatflows.append(chatflow)

    logger.info("Filtered chatflows: %d out of %d", len(filtered_chatflows), len(chatflows))
    return filtered_chatflows

def flowise_predict(chatflow_id: str, question: str) -> str:
    """
    Sends a question to a specific chatflow ID via the Flowise API and returns the response text.

    Args:
        chatflow_id (str): The ID of the Flowise chatflow to be used.
        question (str): The question or prompt to send to the chatflow.

    Returns:
        str: The response text from the Flowise API or an error string if something went wrong.
    """
    # Construct the Flowise API URL for predictions
    url = f"{FLOWISE_API_ENDPOINT.rstrip('/')}/api/v1/prediction/{chatflow_id}"
    headers = {
        "Content-Type": "application/json",
    }
    if FLOWISE_API_KEY:
        headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"

    payload = {
        "chatflowId": chatflow_id,
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

def fetch_chatflows() -> list[dict]:
    """
    Fetch a list of all chatflows from the Flowise API.

    Returns:
        list of dict: Each dict contains the 'id' and 'name' of a chatflow.
                      Returns an empty list if there's an error.
    """
    # Construct the Flowise API URL for fetching chatflows
    url = f"{FLOWISE_API_ENDPOINT.rstrip('/')}/api/v1/chatflows"
    headers = {}
    if FLOWISE_API_KEY:
        headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"

    logger.debug(f"Fetching chatflows from {url}")

    try:
        # Send GET request to the Flowise API
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse and simplify the response data
        chatflows_data = response.json()
        simplified_chatflows = [{"id": cf["id"], "name": cf["name"]} for cf in chatflows_data]

        logger.debug(f"Fetched chatflows: {simplified_chatflows}")
        return filter_chatflows(simplified_chatflows)
    except requests.exceptions.RequestException as e:
        # Log and return an empty list on error
        logger.error(f"Error fetching chatflows: {e}")
        return []

# Log key environment variable values
logger.info(f"Flowise API Key (redacted): {redact_api_key(FLOWISE_API_KEY)}")
logger.info(f"Flowise API Endpoint: {FLOWISE_API_ENDPOINT}")
