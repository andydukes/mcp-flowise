import unittest
from unittest.mock import patch, MagicMock
from mcp_flowise.utils import redact_api_key, setup_logging
import os
import logging
import tempfile
from io import StringIO


class TestUtilsLogging(unittest.TestCase):
    """
    Unit tests for logging utilities and API key redaction in utils.py.
    """

    def setUp(self):
        """
        Reset the logger before each test to ensure no residual handlers.
        """
        logger = logging.getLogger('mcp_flowise.utils')
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    def tearDown(self):
        """
        Remove all handlers after each test.
        """
        logger = logging.getLogger('mcp_flowise.utils')
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    def test_redact_api_key(self):
        """
        Test the redaction of API keys for safe logging.
        """
        self.assertEqual(redact_api_key("1234567890"), "12******90")
        self.assertEqual(redact_api_key("abcd"), "<not set>")  # Too short to redact
        self.assertEqual(redact_api_key("xy"), "<not set>")
        self.assertEqual(redact_api_key(""), "<not set>")
        self.assertEqual(redact_api_key(None), "<not set>")

    @patch("os.makedirs", side_effect=PermissionError("No permission to create logs"))
    def test_setup_logging_error(self, mock_makedirs):
        """
        Test logging setup handling when directory creation fails.
        """
        with patch('sys.stderr', new=StringIO()) as fake_stderr:
            logger = setup_logging(debug=True, log_dir="test_logs", log_file="test.log")
            self.assertTrue(logger)
        # Check that the error message was printed to stderr
        self.assertIn("Failed to create log file handler: No permission to create logs", fake_stderr.getvalue())

    def test_setup_logging_debug(self):
        """
        Test logging setup with debug mode enabled.
        """
        with tempfile.TemporaryDirectory() as temp_log_dir:
            with patch("os.makedirs") as mock_makedirs:
                # Ensure os.makedirs does not raise an exception
                mock_makedirs.return_value = None
                logger = setup_logging(debug=True, log_dir=temp_log_dir, log_file="test.log")
                self.assertTrue(logger)
                mock_makedirs.assert_called_once_with(temp_log_dir, exist_ok=True)
                self.assertEqual(logger.level, logging.DEBUG)
                # Verify that handlers are added
                self.assertEqual(len(logger.handlers), 2)
                # Check that the first handler is FileHandler with DEBUG level
                self.assertIsInstance(logger.handlers[0], logging.FileHandler)
                self.assertEqual(logger.handlers[0].level, logging.DEBUG)
                # Check that the second handler is StreamHandler with ERROR level
                self.assertIsInstance(logger.handlers[1], logging.StreamHandler)
                self.assertEqual(logger.handlers[1].level, logging.ERROR)

    def test_setup_logging_info(self):
        """
        Test logging setup with info mode (default).
        """
        with tempfile.TemporaryDirectory() as temp_log_dir:
            with patch("os.makedirs") as mock_makedirs:
                # Ensure os.makedirs does not raise an exception
                mock_makedirs.return_value = None
                logger = setup_logging(debug=False, log_dir=temp_log_dir, log_file="test.log")
                self.assertTrue(logger)
                mock_makedirs.assert_called_once_with(temp_log_dir, exist_ok=True)
                self.assertEqual(logger.level, logging.INFO)
                # Verify that handlers are added
                self.assertEqual(len(logger.handlers), 2)
                # Check that the first handler is FileHandler with INFO level
                self.assertIsInstance(logger.handlers[0], logging.FileHandler)
                self.assertEqual(logger.handlers[0].level, logging.INFO)
                # Check that the second handler is StreamHandler with ERROR level
                self.assertIsInstance(logger.handlers[1], logging.StreamHandler)
                self.assertEqual(logger.handlers[1].level, logging.ERROR)


if __name__ == "__main__":
    unittest.main()
