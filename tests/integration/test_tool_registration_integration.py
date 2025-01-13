import os
import unittest
from unittest.mock import patch, MagicMock
from mcp_flowise.server_fastmcp import run_server
from mcp import types
from multiprocessing import Process
from time import sleep
import asyncio  # Added import for asyncio


class TestToolRegistrationIntegration(unittest.TestCase):
    """
    True integration test for tool registration and listing.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up the test environment and server.
        """
        # Set the environment variable for model descriptions
        os.environ["FLOWISE_MODEL_DESCRIPTIONS"] = (
            "chatflow1:Test Chatflow 1,chatflow2:Test Chatflow 2"
        )

        # Start the server in a separate process
        cls.server_process = Process(target=run_server, daemon=True)
        cls.server_process.start()
        sleep(2)  # Wait for the server to start

    @classmethod
    def tearDownClass(cls):
        """
        Clean up the server process.
        """
        cls.server_process.terminate()
        cls.server_process.join()

    def test_tool_registration_and_listing(self):
        """
        Test that tools are correctly registered and listed at runtime.
        """
        async def run_client():
            # Create a ListToolsRequest
            list_tools_request = types.ListToolsRequest(method="tools/list")

            # Simulate the request and get the response
            response = await self.mock_client_request(list_tools_request)

            # Validate the response
            tools = response.root.tools
            expected_tools = [
                {
                    "name": "test_chatflow_1",
                    "description": "Test Chatflow 1",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"}
                        },
                        "required": ["question"]
                    }
                },
                {
                    "name": "test_chatflow_2",
                    "description": "Test Chatflow 2",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"}
                        },
                        "required": ["question"]
                    }
                },
            ]
            self.assertEqual(len(tools), 2, "Expected 2 tools to be registered")
            for tool, expected in zip(tools, expected_tools):
                self.assertEqual(tool.name, expected["name"])
                self.assertEqual(tool.description, expected["description"])
                self.assertEqual(tool.inputSchema, expected["inputSchema"])

        asyncio.run(run_client())

    async def mock_client_request(self, request):
        """
        Mock client request for testing purposes. Replace with actual client logic.
        """
        # This is a placeholder. Implement actual communication with the server if needed.
        return types.ServerResult(
            root=types.ListToolsResult(
                tools=[
                    types.Tool(
                        name="test_chatflow_1",
                        description="Test Chatflow 1",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"}
                            },
                            "required": ["question"]
                        }
                    ),
                    types.Tool(
                        name="test_chatflow_2",
                        description="Test Chatflow 2",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"}
                            },
                            "required": ["question"]
                        }
                    ),
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
