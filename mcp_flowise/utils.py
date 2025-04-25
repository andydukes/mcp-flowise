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
import json
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Flowise API configuration
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "")
FLOWISE_API_ENDPOINT = os.getenv("FLOWISE_API_ENDPOINT", "http://localhost:3010")


def setup_logging(debug: bool = False, log_dir: str = None, log_file: str = "debug-mcp-flowise.log") -> logging.Logger:
    """
    Sets up logging for the application, including outputting CRITICAL and ERROR logs to stdout.

    Args:
        debug (bool): If True, set log level to DEBUG; otherwise, INFO.
        log_dir (str): Directory where log files will be stored. Ignored if `FLOWISE_LOGFILE_PATH` is set.
        log_file (str): Name of the log file. Ignored if `FLOWISE_LOGFILE_PATH` is set.

    Returns:
        logging.Logger: Configured logger instance.
    """
    log_path = os.getenv("FLOWISE_LOGFILE_PATH")
    if not log_path:
        if log_dir is None:
            log_dir = os.path.join(os.path.expanduser("~"), "mcp_logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, log_file)
        except PermissionError as e:
            # Fallback to stdout logging if directory creation fails
            log_path = None
            print(f"[ERROR] Failed to create log directory: {e}", file=sys.stderr)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False  # Prevent log messages from propagating to the root logger

    # Remove all existing handlers to prevent accumulation
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    handlers = []

    if log_path:
        try:
            file_handler = logging.FileHandler(log_path, mode="a")
            file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
            formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s")
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception as e:
            print(f"[ERROR] Failed to create log file handler: {e}", file=sys.stderr)

    # Attempt to create StreamHandler for ERROR level logs
    try:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        stdout_handler.setFormatter(formatter)
        handlers.append(stdout_handler)
    except Exception as e:
        print(f"[ERROR] Failed to create stdout log handler: {e}", file=sys.stderr)

    # Add all handlers to the logger
    for handler in handlers:
        logger.addHandler(handler)

    if log_path:
        logger.debug(f"Logging initialized. Writing logs to {log_path}")
    else:
        logger.debug("Logging initialized. Logs will only appear in stdout.")
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


def filter_chatflows(chatflows: list[dict]) -> list[dict]:
    """
    Filters chatflows based on whitelist and blacklist criteria.
    Whitelist takes precedence over blacklist.

    Args:
        chatflows (list[dict]): A list of chatflow dictionaries.

    Returns:
        list[dict]: Filtered list of chatflows.
    """
    logger = logging.getLogger(__name__)

    # Dynamically fetch filtering criteria
    whitelist_ids = set(filter(bool, os.getenv("FLOWISE_WHITELIST_ID", "").split(",")))
    blacklist_ids = set(filter(bool, os.getenv("FLOWISE_BLACKLIST_ID", "").split(",")))
    whitelist_name_regex = os.getenv("FLOWISE_WHITELIST_NAME_REGEX", "")
    blacklist_name_regex = os.getenv("FLOWISE_BLACKLIST_NAME_REGEX", "")

    filtered_chatflows = []

    for chatflow in chatflows:
        chatflow_id = chatflow.get("id", "")
        chatflow_name = chatflow.get("name", "")

        # Flags to determine inclusion
        is_whitelisted = False

        # Check Whitelist
        if whitelist_ids or whitelist_name_regex:
            if whitelist_ids and chatflow_id in whitelist_ids:
                is_whitelisted = True
            if whitelist_name_regex and re.search(whitelist_name_regex, chatflow_name):
                is_whitelisted = True

            if is_whitelisted:
                # If whitelisted, include regardless of blacklist
                logger.debug("Including whitelisted chatflow '%s' (ID: '%s').", chatflow_name, chatflow_id)
                filtered_chatflows.append(chatflow)
                continue  # Skip blacklist checks
            else:
                # If not whitelisted, exclude regardless of blacklist
                logger.debug("Excluding non-whitelisted chatflow '%s' (ID: '%s').", chatflow_name, chatflow_id)
                continue
        else:
            # If no whitelist, apply blacklist directly
            if blacklist_ids and chatflow_id in blacklist_ids:
                logger.debug("Skipping chatflow '%s' (ID: '%s') - In blacklist.", chatflow_name, chatflow_id)
                continue  # Exclude blacklisted by ID
            if blacklist_name_regex and re.search(blacklist_name_regex, chatflow_name):
                logger.debug("Skipping chatflow '%s' (ID: '%s') - Name matches blacklist regex.", chatflow_name, chatflow_id)
                continue  # Exclude blacklisted by name

            # Include the chatflow if it passes all filters
            logger.debug("Including chatflow '%s' (ID: '%s').", chatflow_name, chatflow_id)
            filtered_chatflows.append(chatflow)

    logger.debug("Filtered chatflows: %d out of %d", len(filtered_chatflows), len(chatflows))
    return filtered_chatflows

def flowise_predict(chatflow_id: str, question: str) -> str:
    """
    Sends a question to a specific chatflow ID via the Flowise API and returns the response JSON text.

    Args:
        chatflow_id (str): The ID of the Flowise chatflow to be used.
        question (str): The question or prompt to send to the chatflow.

    Returns:
        str: The raw JSON response text from the Flowise API, or an error message if something goes wrong.
    """
    logger = logging.getLogger(__name__)

    # Construct the Flowise API URL for predictions
    url = f"{FLOWISE_API_ENDPOINT.rstrip('/')}/api/v1/prediction/{chatflow_id}"
    headers = {
        "Content-Type": "application/json",
    }
    if FLOWISE_API_KEY:
        headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"

    payload = {"question": question}
    logger.debug(f"Sending prediction request to {url} with payload: {payload}")

    try:
        # Send POST request to the Flowise API
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        logger.debug(f"Prediction response code: HTTP {response.status_code}")
        # response.raise_for_status()

        # Log the raw response text for debugging
        logger.debug(f"Raw prediction response: {response.text}")

        # Return the raw JSON response text
        return response.text

    #except requests.exceptions.RequestException as e:
    except Exception as e:
        # Log and return an error message
        logger.error(f"Error during prediction: {e}")
        return json.dumps({"error": str(e)})


def fetch_chatflows() -> list[dict]:
    """
    Fetch a list of all chatflows from the Flowise API.

    Returns:
        list of dict: Each dict contains the 'id' and 'name' of a chatflow.
                      Returns an empty list if there's an error.
    """
    logger = logging.getLogger(__name__)

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
    #except requests.exceptions.RequestException as e:
    except Exception as e:
        # Log and return an empty list on error
        logger.error(f"Error fetching chatflows: {e}")
        return []


# Set up logging before obtaining the logger
DEBUG = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
logger = setup_logging(debug=DEBUG)

# Log key environment variable values
logger.debug(f"Flowise API Key (redacted): {redact_api_key(FLOWISE_API_KEY)}")
logger.debug(f"Flowise API Endpoint: {FLOWISE_API_ENDPOINT}")
