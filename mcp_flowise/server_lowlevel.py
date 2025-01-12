'''
Low-Level Server for the Flowise MCP.

This server dynamically registers tools based on the provided chatflows in 
the FLOWISE_CHATFLOW_DESCRIPTIONS environment variable.

Each chatflow is described in the format:
    "chatflow_id1:description1,chatflow_id2:description2,..."
'''

import os
import re
import sys
import logging
import asyncio
from typing import List, Dict
from dotenv import load_dotenv
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp_flowise.utils import flowise_predict, redact_api_key

# Global tool mapping: tool name to chatflow ID
NAME_TO_ID_MAPPING = {}

# Load environment variables from .env if present
load_dotenv()

# Configure logging
DEBUG = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Initialize the Low-Level MCP Server
mcp = Server("FlowiseMCP-with-EnvAuth")


def parse_chatflow_descriptions() -> List[Dict[str, str]]:
    '''
    Parse and validate the FLOWISE_CHATFLOW_DESCRIPTIONS environment variable.

    Returns:
        A list of dictionaries containing 'id' and 'description' for each chatflow.

    Raises:
        ValueError: If the environment variable is not set or has an invalid format.
    '''
    FLOWISE_CHATFLOW_DESCRIPTIONS = os.getenv("FLOWISE_CHATFLOW_DESCRIPTIONS")
    logger.debug("Retrieved FLOWISE_CHATFLOW_DESCRIPTIONS: %s", FLOWISE_CHATFLOW_DESCRIPTIONS)

    if not FLOWISE_CHATFLOW_DESCRIPTIONS:
        logger.error("FLOWISE_CHATFLOW_DESCRIPTIONS is not set.")
        raise ValueError("FLOWISE_CHATFLOW_DESCRIPTIONS environment variable must be set.")

    chatflows = []
    pairs = FLOWISE_CHATFLOW_DESCRIPTIONS.split(",")

    for pair in pairs:
        if ":" not in pair:
            logger.error("Invalid chatflow format detected: %s", pair)
            raise ValueError(f"Invalid chatflow format: {pair}. Expected 'chatflow_id:description'.")

        chatflow_id, description = pair.split(":", 1)
        chatflow_id = chatflow_id.strip()
        description = description.strip()

        if not chatflow_id or not description:
            logger.error("Empty chatflow_id or description found in pair: %s", pair)
            raise ValueError(f"Empty chatflow_id or description in: {pair}.")

        logger.debug("Parsed chatflow - ID: %s, Description: %s", chatflow_id, description)
        chatflows.append({"id": chatflow_id, "description": description})

    logger.info("Successfully parsed %d chatflows.", len(chatflows))
    return chatflows


def normalize_tool_name(name: str) -> str:
    '''
    Normalize tool names by converting to lowercase and replacing non-alphanumeric characters with underscores.

    Args:
        name (str): Original tool name.

    Returns:
        str: Normalized tool name.
    '''
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", name).lower()
    logger.debug("Normalized tool name from '%s' to '%s'", name, normalized)
    return normalized


def create_prediction_tool(chatflow_id: str, description: str) -> types.Tool:
    '''
    Create a tool dynamically for a given chatflow.

    Args:
        chatflow_id (str): The unique ID of the chatflow.
        description (str): The human-readable description of the chatflow.

    Returns:
        Tool: A dynamically created Tool object.

    Raises:
        ValueError: If the chatflow_id contains invalid characters.
    '''
    if not re.match(r"^[a-zA-Z0-9_-]+$", chatflow_id):
        logger.error("Invalid chatflow_id: %s. Only alphanumeric, dashes, and underscores are allowed.", chatflow_id)
        raise ValueError(f"Invalid chatflow_id: {chatflow_id}. Only alphanumeric, dashes, and underscores are allowed.")

    normalized_name = normalize_tool_name(description)
    if normalized_name in NAME_TO_ID_MAPPING:
        logger.warning("Tool name '%s' already exists. Overwriting with new chatflow_id '%s'.", normalized_name, chatflow_id)
    NAME_TO_ID_MAPPING[normalized_name] = chatflow_id

    logger.debug("Creating prediction tool for chatflow_id: %s, description: %s", chatflow_id, description)

    return types.Tool(
        name=normalized_name,
        description=description,
        inputSchema={
            "type": "object",
            "required": ["question"],
            "properties": {"question": {"type": "string"}},
        },
    )


async def dispatcher_handler(request: types.CallToolRequest) -> types.ServerResult:
    '''
    Dispatcher handler that routes CallToolRequest to the appropriate tool handler based on the tool name.

    Args:
        request (types.CallToolRequest): The incoming tool call request.

    Returns:
        types.ServerResult: The result of the tool execution.
    '''
    tool_name = request.tool_name
    logger.debug("Dispatcher received CallToolRequest for tool: %s", tool_name)

    if tool_name not in NAME_TO_ID_MAPPING:
        logger.error("Unknown tool requested: %s", tool_name)
        return types.ServerResult(
            root=types.CallToolResult(
                content=[types.TextContent(type="text", text='Unknown tool requested')]
            )
        )

    chatflow_id = NAME_TO_ID_MAPPING[tool_name]
    question = request.params.arguments.get("question")

    if not question:
        logger.error("Missing 'question' argument in request for tool: %s", tool_name)
        return types.ServerResult(
            root=types.CallToolResult(
                content=[types.TextContent(type="text", text='Missing "question" argument')]
            )
        )

    logger.debug("Dispatching prediction for chatflow_id: %s with question: %s", chatflow_id, question)
    try:
        result = flowise_predict(chatflow_id, question)
        logger.debug("Received prediction result: %s", result)
    except Exception as e:
        logger.error("Error during prediction for tool '%s': %s", tool_name, e)
        result = f"Error: {str(e)}"

    return types.ServerResult(
        root=types.CallToolResult(
            content=[types.TextContent(type="text", text=result)]
        )
    )


def run_server():
    '''
    Run the Low-Level Flowise server by registering tools dynamically.
    '''
    try:
        chatflows = parse_chatflow_descriptions()
    except ValueError as e:
        logger.critical("Failed to start server: %s", e)
        sys.exit(1)

    tools = []
    for chatflow in chatflows:
        try:
            tool = create_prediction_tool(chatflow["id"], chatflow["description"])
            tools.append(tool)
            logger.info("Registered tool: %s", tool.name)
        except Exception as e:
            logger.error("Error while creating tool for chatflow %s: %s", chatflow['id'], e)

    if not tools:
        logger.critical("No valid tools registered. Shutting down the server.")
        sys.exit(1)

    # Register the dispatcher handler once after all tools are created
    mcp.request_handlers[types.CallToolRequest] = dispatcher_handler
    logger.debug("Registered dispatcher_handler for CallToolRequest.")

    # Register the tool listing endpoint
    async def list_tools(request: types.ListToolsRequest) -> types.ServerResult:
        '''
        Handle the list tools request by returning the list of registered tools.

        Args:
            request (types.ListToolsRequest): The incoming list tools request.

        Returns:
            types.ServerResult: The list of tools.
        '''
        logger.debug("Handling list_tools request.")
        return types.ServerResult(root=types.ListToolsResult(tools=tools))

    mcp.request_handlers[types.ListToolsRequest] = list_tools
    logger.debug("Registered list_tools handler.")

    # Start the server
    async def start_server():
        '''
        Asynchronously start the MCP server with standard I/O transport.
        '''
        logger.info("Starting Low-Level MCP server...")
        try:
            async with stdio_server() as (read_stream, write_stream):
                await mcp.run(
                    read_stream,
                    write_stream,
                    initialization_options=InitializationOptions(
                        server_name="FlowiseMCP-with-EnvAuth",
                        server_version="0.1.0",
                        capabilities=types.ServerCapabilities(),
                    ),
                )
        except Exception as e:
            logger.critical("Unhandled exception in MCP server: %s", e)
            sys.exit(1)

    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("MCP server shutdown initiated by user.")
    except Exception as e:
        logger.critical("Failed to start MCP server: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    run_server()
