import os
import unittest
from unittest.mock import patch
from mcp_flowise.utils import filter_models  # Updated to accept list
from mcp_flowise.utils import fetch_chatflows


class TestModelFilters(unittest.TestCase):
    """
    Unit tests for model filtering logic in mcp_flowise.utils.
    Covers both chatflows and assistants.
    """

    def setUp(self):
        """
        Reset the environment variables for filtering logic.
        """
        # Chatflow Environment Variables
        os.environ.pop("FLOWISE_WHITELIST_CHATFLOW_IDS", None)
        os.environ.pop("FLOWISE_BLACKLIST_CHATFLOW_IDS", None)
        os.environ.pop("FLOWISE_WHITELIST_CHATFLOW_NAME_REGEX", None)
        os.environ.pop("FLOWISE_BLACKLIST_CHATFLOW_NAME_REGEX", None)

        # Assistant Environment Variables
        os.environ.pop("FLOWISE_WHITELIST_ASSISTANT_IDS", None)
        os.environ.pop("FLOWISE_BLACKLIST_ASSISTANT_IDS", None)
        os.environ.pop("FLOWISE_WHITELIST_ASSISTANT_NAME_REGEX", None)
        os.environ.pop("FLOWISE_BLACKLIST_ASSISTANT_NAME_REGEX", None)

    # --- Chatflow Tests ---

    def test_chatflow_no_filters(self):
        """
        Test that all chatflows are returned when no filters are set.
        """
        chatflows = [
            {"id": "chatflow1", "name": "First Chatflow"},
            {"id": "chatflow2", "name": "Second Chatflow"},
        ]
        assistants = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["chatflows"], "chatflow")
        self.assertEqual(len(filtered), len(chatflows))
        self.assertListEqual(filtered, chatflows)

    @patch.dict(os.environ, {"FLOWISE_WHITELIST_CHATFLOW_IDS": "chatflow1,chatflow3"})
    def test_chatflow_whitelist_id_filter(self):
        """
        Test that only whitelisted chatflows by ID are returned.
        """
        chatflows = [
            {"id": "chatflow1", "name": "First Chatflow"},
            {"id": "chatflow2", "name": "Second Chatflow"},
            {"id": "chatflow3", "name": "Third Chatflow"},
        ]
        assistants = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["chatflows"], "chatflow")
        self.assertEqual(len(filtered), 2)
        self.assertTrue(all(cf["id"] in {"chatflow1", "chatflow3"} for cf in filtered))

    @patch.dict(os.environ, {"FLOWISE_BLACKLIST_CHATFLOW_IDS": "chatflow2"})
    def test_chatflow_blacklist_id_filter(self):
        """
        Test that blacklisted chatflows by ID are excluded.
        """
        chatflows = [
            {"id": "chatflow1", "name": "First Chatflow"},
            {"id": "chatflow2", "name": "Second Chatflow"},
        ]
        assistants = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["chatflows"], "chatflow")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "chatflow1")

    @patch.dict(os.environ, {"FLOWISE_WHITELIST_CHATFLOW_NAME_REGEX": ".*First.*"})
    def test_chatflow_whitelist_name_regex_filter(self):
        """
        Test that only chatflows matching the whitelist name regex are returned.
        """
        chatflows = [
            {"id": "chatflow1", "name": "First Chatflow"},
            {"id": "chatflow2", "name": "Second Chatflow"},
        ]
        assistants = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["chatflows"], "chatflow")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "First Chatflow")

    @patch.dict(os.environ, {"FLOWISE_BLACKLIST_CHATFLOW_NAME_REGEX": ".*Second.*"})
    def test_chatflow_blacklist_name_regex_filter(self):
        """
        Test that chatflows matching the blacklist name regex are excluded.
        """
        chatflows = [
            {"id": "chatflow1", "name": "First Chatflow"},
            {"id": "chatflow2", "name": "Second Chatflow"},
        ]
        assistants = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["chatflows"], "chatflow")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "First Chatflow")

    @patch.dict(
        os.environ,
        {
            "FLOWISE_WHITELIST_CHATFLOW_IDS": "chatflow1",
            "FLOWISE_BLACKLIST_CHATFLOW_NAME_REGEX": ".*Second.*",
        },
    )
    def test_chatflow_whitelist_and_blacklist_combined(self):
        """
        Test that whitelist takes precedence over blacklist for chatflows.
        """
        chatflows = [
            {"id": "chatflow1", "name": "Second Chatflow"},
            {"id": "chatflow2", "name": "Another Chatflow"},
        ]
        assistants = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["chatflows"], "chatflow")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "chatflow1")

    # --- Assistant Tests ---

    def test_assistant_no_filters(self):
        """
        Test that all assistants are returned when no filters are set.
        """
        assistants = [
            {"id": "assistant1", "name": "First Assistant"},
            {"id": "assistant2", "name": "Second Assistant"},
        ]
        chatflows = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["assistants"], "assistant")
        self.assertEqual(len(filtered), len(assistants))
        self.assertListEqual(filtered, assistants)

    @patch.dict(os.environ, {"FLOWISE_WHITELIST_ASSISTANT_IDS": "assistant1,assistant3"})
    def test_assistant_whitelist_id_filter(self):
        """
        Test that only whitelisted assistants by ID are returned.
        """
        assistants = [
            {"id": "assistant1", "name": "First Assistant"},
            {"id": "assistant2", "name": "Second Assistant"},
            {"id": "assistant3", "name": "Third Assistant"},
        ]
        chatflows = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["assistants"], "assistant")
        self.assertEqual(len(filtered), 2)
        self.assertTrue(all(asst["id"] in {"assistant1", "assistant3"} for asst in filtered))

    @patch.dict(os.environ, {"FLOWISE_BLACKLIST_ASSISTANT_IDS": "assistant2"})
    def test_assistant_blacklist_id_filter(self):
        """
        Test that blacklisted assistants by ID are excluded.
        """
        assistants = [
            {"id": "assistant1", "name": "First Assistant"},
            {"id": "assistant2", "name": "Second Assistant"},
        ]
        chatflows = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["assistants"], "assistant")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "assistant1")

    @patch.dict(os.environ, {"FLOWISE_WHITELIST_ASSISTANT_NAME_REGEX": ".*First.*"})
    def test_assistant_whitelist_name_regex_filter(self):
        """
        Test that only assistants matching the whitelist name regex are returned.
        """
        assistants = [
            {"id": "assistant1", "name": "First Assistant"},
            {"id": "assistant2", "name": "Second Assistant"},
        ]
        chatflows = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["assistants"], "assistant")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "First Assistant")

    @patch.dict(os.environ, {"FLOWISE_BLACKLIST_ASSISTANT_NAME_REGEX": ".*Second.*"})
    def test_assistant_blacklist_name_regex_filter(self):
        """
        Test that assistants matching the blacklist name regex are excluded.
        """
        assistants = [
            {"id": "assistant1", "name": "First Assistant"},
            {"id": "assistant2", "name": "Second Assistant"},
        ]
        chatflows = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["assistants"], "assistant")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "First Assistant")

    @patch.dict(
        os.environ,
        {
            "FLOWISE_WHITELIST_ASSISTANT_IDS": "assistant1",
            "FLOWISE_BLACKLIST_ASSISTANT_NAME_REGEX": ".*Second.*",
        },
    )
    def test_assistant_whitelist_and_blacklist_combined(self):
        """
        Test that whitelist takes precedence over blacklist for assistants.
        """
        assistants = [
            {"id": "assistant1", "name": "Second Assistant"},
            {"id": "assistant2", "name": "Another Assistant"},
        ]
        chatflows = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["assistants"], "assistant")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "assistant1")

    # --- Additional Chatflow Tests ---

    @patch.dict(os.environ, {"FLOWISE_WHITELIST_CHATFLOW_IDS": "chatflow1,chatflow3"})
    def test_chatflow_whitelist_id_filter_multiple(self):
        """
        Additional test to ensure multiple whitelisted IDs are handled correctly.
        """
        chatflows = [
            {"id": "chatflow1", "name": "First Chatflow"},
            {"id": "chatflow3", "name": "Third Chatflow"},
            {"id": "chatflow4", "name": "Fourth Chatflow"},
        ]
        assistants = []
        all_models = {"chatflows": chatflows, "assistants": assistants}
        filtered = filter_models(all_models["chatflows"], "chatflow")
        self.assertEqual(len(filtered), 2)
        self.assertTrue(all(cf["id"] in {"chatflow1", "chatflow3"} for cf in filtered))


if __name__ == "__main__":
    unittest.main()
