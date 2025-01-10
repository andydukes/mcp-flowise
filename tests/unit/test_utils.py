import unittest
from unittest.mock import patch, Mock
import requests
from mcp_flowise.utils import redact_api_key, flowise_predict, fetch_chatflows

class TestUtils(unittest.TestCase):

    def test_redact_api_key(self):
        """
        Test redaction of API keys.
        """
        self.assertEqual(redact_api_key("1234567890"), "12******90")
        self.assertEqual(redact_api_key("abcd"), "<not set>")  # Short key expected behavior.
        self.assertEqual(redact_api_key("xy"), "<not set>")
        self.assertEqual(redact_api_key(""), "<not set>")
        self.assertEqual(redact_api_key(None), "<not set>")

    @patch("requests.post")
    def test_flowise_predict_success(self, mock_post):
        """
        Test successful prediction response.
        """
        mock_post.return_value = Mock(status_code=200, text="Mock Prediction")
        response = flowise_predict("valid_chatflow_id", "What's AI?")
        self.assertEqual(response, "Mock Prediction")
        mock_post.assert_called_once()

    @patch("requests.post", side_effect=requests.Timeout)
    def test_flowise_predict_timeout(self, mock_post):
        """
        Test prediction handling of timeout.
        """
        response = flowise_predict("valid_chatflow_id", "What's AI?")
        self.assertIn("Error:", response)
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_flowise_predict_http_error(self, mock_post):
        """
        Test prediction handling of HTTP errors.
        """
        mock_post.return_value = Mock(status_code=500, raise_for_status=Mock(side_effect=requests.HTTPError("500 Error")))
        response = flowise_predict("valid_chatflow_id", "What's AI?")
        self.assertIn("Error:", response)
        mock_post.assert_called_once()

    @patch("requests.get")
    def test_fetch_chatflows_success(self, mock_get):
        """
        Test successful chatflow fetching.
        """
        mock_get.return_value = Mock(status_code=200, json=Mock(return_value=[
            {"id": "chatflow1", "name": "Chatflow One"},
            {"id": "chatflow2", "name": "Chatflow Two"},
        ]))
        chatflows = fetch_chatflows()
        self.assertEqual(len(chatflows), 2)
        self.assertEqual(chatflows[0]["id"], "chatflow1")
        mock_get.assert_called_once()

    @patch("requests.get", side_effect=requests.ConnectionError("Connection Error"))
    def test_fetch_chatflows_connection_error(self, mock_get):
        """
        Test chatflow fetching connection error.
        """
        chatflows = fetch_chatflows()
        self.assertEqual(chatflows, [])
        mock_get.assert_called_once()

    @patch("requests.get", side_effect=requests.Timeout)
    def test_fetch_chatflows_timeout(self, mock_get):
        """
        Test chatflow fetching timeout.
        """
        chatflows = fetch_chatflows()
        self.assertEqual(chatflows, [])
        mock_get.assert_called_once()

