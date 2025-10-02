#!/usr/bin/env python3
"""
Comprehensive tests for entrypoint.py to achieve 100% coverage.
"""

import subprocess
import sys
from unittest.mock import Mock, patch

import entrypoint


class TestEntrypoint:
    """Test class for entrypoint.py coverage."""

    @patch("entrypoint.Path")
    @patch("sys.exit")
    def test_main_server_file_not_found(self, mock_exit, mock_path):
        """Test main function when server file doesn't exist."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance

        with patch("builtins.print") as mock_print:
            entrypoint.main()

        mock_print.assert_any_call("❌ Error: openapi_server.py not found")
        mock_exit.assert_called_once_with(1)

    @patch("entrypoint.Path")
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_main_successful_execution(self, mock_exit, mock_subprocess, mock_path):
        """Test main function with successful server execution."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        with patch("builtins.print") as mock_print:
            entrypoint.main()

        mock_print.assert_any_call("🚀 BMC AMI DevX Code Pipeline FastMCP Server")
        mock_subprocess.assert_called_once_with(
            [sys.executable, "openapi_server.py"], check=True
        )
        mock_exit.assert_called_once_with(0)

    @patch("entrypoint.Path")
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_main_keyboard_interrupt(self, mock_exit, mock_subprocess, mock_path):
        """Test main function handles KeyboardInterrupt."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        mock_subprocess.side_effect = KeyboardInterrupt()

        with patch("builtins.print") as mock_print:
            entrypoint.main()

        mock_print.assert_any_call("\n🛑 Server interrupted by user")
        mock_exit.assert_called_once_with(0)

    @patch("entrypoint.Path")
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_main_subprocess_exception(self, mock_exit, mock_subprocess, mock_path):
        """Test main function handles subprocess exceptions."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        mock_subprocess.side_effect = Exception("Test error")

        with patch("builtins.print") as mock_print:
            entrypoint.main()

        mock_print.assert_any_call("❌ Error starting server: Test error")
        mock_exit.assert_called_once_with(1)

    @patch("entrypoint.Path")
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_main_non_zero_exit(self, mock_exit, mock_subprocess, mock_path):
        """Test main function with non-zero subprocess exit code."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        mock_result = Mock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        entrypoint.main()

        mock_exit.assert_called_once_with(1)

    def test_startup_messages(self):
        """Test that main function prints correct startup messages."""
        with (
            patch("entrypoint.Path") as mock_path,
            patch("subprocess.run") as mock_subprocess,
            patch("sys.exit"),
            patch("builtins.print") as mock_print,
        ):

            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance

            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result

            entrypoint.main()

            expected_calls = [
                "🚀 BMC AMI DevX Code Pipeline FastMCP Server",
                "📁 Server File: openapi_server.py",
                "🏗️  FastMCP with Enterprise Features:",
                "   ✅ Rate limiting with token bucket algorithm",
                "   ✅ LRU/TTL caching with comprehensive management",
            ]

            for expected_call in expected_calls:
                mock_print.assert_any_call(expected_call)

    def test_module_attributes(self):
        """Test entrypoint module has expected attributes."""
        assert entrypoint.__doc__ is not None
        assert (
            "Entry point for BMC AMI DevX Code Pipeline FastMCP Server"
            in entrypoint.__doc__
        )
        assert hasattr(entrypoint, "sys")
        assert hasattr(entrypoint, "Path")

    @patch("entrypoint.Path")
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_calledprocesserror_handling(self, mock_exit, mock_subprocess, mock_path):
        """Test handling of CalledProcessError."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "cmd")

        with patch("builtins.print") as mock_print:
            entrypoint.main()

        mock_print.assert_any_call(
            "❌ Error starting server: Command 'cmd' returned non-zero exit status 1."
        )
        mock_exit.assert_called_once_with(1)

    def test_main_function_callable(self):
        """Test that main function exists and is callable."""
        assert hasattr(entrypoint, "main")
        assert callable(entrypoint.main)

    def test_constants_usage(self):
        """Test entrypoint uses correct constants."""
        with (
            patch("entrypoint.Path") as mock_path,
            patch("subprocess.run") as mock_subprocess,
            patch("sys.exit"),
            patch("builtins.print"),
        ):

            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance

            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result

            entrypoint.main()

            mock_path.assert_called_with("openapi_server.py")
            mock_subprocess.assert_called_once_with(
                [sys.executable, "openapi_server.py"], check=True
            )
