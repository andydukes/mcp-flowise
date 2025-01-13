"""
Provides the FastMCP server logic for mcp_flowise.

This server exposes a limited set of tools (list_chatflows, create_prediction)
and uses environment variables to determine the chatflow or assistant configuration.
"""

import os
import sys
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp_flowise.utils import flowise_predict, fetch_chatflows, redact_api_key, setup_logging

# Load environment variables from .env if present
load_dotenv()

# Environment variables
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "")
FLOWISE_API_ENDPOINT = os.getenv("FLOWISE_API_ENDPOINT", "http://localhost:3000")
FLOWISE_CHATFLOW_ID = os.getenv("FLOWISE_CHATFLOW_ID")
FLOWISE_ASSISTANT_ID = os.getenv("FLOWISE_ASSISTANT_ID")
FLOWISE_CHATFLOW_DESCRIPTION = os.getenv("FLOWISE_CHATFLOW_DESCRIPTION")

DEBUG = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")

# Configure logging
logger = setup_logging(debug=DEBUG)

# Log key environment variable values
logger.debug(f"Flowise API Key (redacted): {redact_api_key(FLOWISE_API_KEY)}")
logger.debug(f"Flowise API Endpoint: {FLOWISE_API_ENDPOINT}")
logger.debug(f"Flowise Chatflow ID: {FLOWISE_CHATFLOW_ID}")
logger.debug(f"Flowise Assistant ID: {FLOWISE_ASSISTANT_ID}")
logger.debug(f"Flowise Chatflow Description: {FLOWISE_CHATFLOW_DESCRIPTION}")

# Initialize MCP Server
mcp = FastMCP("FlowiseMCP-with-EnvAuth", dependencies=["requests"])


@mcp.tool()
def list_chatflows() -> str:
    """
    List all available chatflows from the Flowise API.

    Returns:
        str: A JSON-encoded string of filtered chatflows.
    """
    logger.debug("Handling list_chatflows tool.")
    chatflows = fetch_chatflows()

    logger.debug(f"Filtered chatflows: {chatflows}")
    return json.dumps(chatflows)


@mcp.tool()
def create_prediction(*, model_type: str, model_id: str, question: str) -> str:
    """
    Create a prediction by sending a question to a specific chatflow or assistant.

    Args:
        model_type (str): Type of model ('chatflow' or 'assistant').
        model_id (str): The ID of the Flowise model to be used.
        question (str): The question or prompt to send to the chatflow.

    Returns:
        str: The prediction result or an error message.
    """
    logger.debug(f"create_prediction called with model_type={model_type}, model_id={model_id}, question={question}")
    
    if not model_id:
        logger.error("No model_id provided for prediction.")
        return "Error: model_id is required."

    return flowise_predict(model_type, model_id, question)


def run_server():
    """
    Run the FastMCP version of the Flowise server.

    This function ensures proper configuration and handles server initialization.

    Raises:
        SystemExit: If both FLOWISE_CHATFLOW_ID and FLOWISE_ASSISTANT_ID are set simultaneously.
    """
    if FLOWISE_CHATFLOW_ID and FLOWISE_ASSISTANT_ID:
        logger.error("Both FLOWISE_CHATFLOW_ID and FLOWISE_ASSISTANT_ID are set. Set only one.")
        sys.exit(1)

    try:
        logger.info("Starting MCP server (FastMCP version)...")
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error("Unhandled exception in MCP server.", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server()
