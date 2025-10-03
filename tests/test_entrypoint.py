#!/usr/bin/env python3
"""
Tests for entrypoint.py

Comprehensive test coverage for the main entry point functionality.
"""

import subprocess
import sys
from unittest.mock import Mock, patch

import pytest


class TestEntrypoint:
    """Test cases for entrypoint.py main function."""

    def test_main_server_file_exists_success(self):
        """Test main() when server file exists and subprocess succeeds."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("sys.exit") as mock_exit,
            patch("builtins.print"),
        ):

            # Configure subprocess to succeed
            mock_run.return_value = Mock(returncode=0)

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify subprocess was called correctly
            mock_run.assert_called_once_with(
                [sys.executable, "openapi_server.py"], check=True
            )
            mock_exit.assert_called_once_with(0)

    def test_main_server_file_missing(self):
        """Test main() when server file doesn't exist."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("sys.exit") as mock_exit,
            patch("builtins.print") as mock_print,
        ):

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify error handling - should be called once with exit code 1
            assert mock_exit.call_count >= 1
            # Check that it was called with 1 at least once
            exit_calls = [call.args[0] for call in mock_exit.call_args_list]
            assert 1 in exit_calls
            mock_print.assert_any_call("❌ Error: openapi_server.py not found")
            mock_print.assert_any_call(
                "Expected: BMC AMI DevX Code Pipeline FastMCP Server"
            )

    def test_main_subprocess_error(self):
        """Test main() when subprocess fails."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("sys.exit") as mock_exit,
            patch("builtins.print") as mock_print,
        ):

            # Configure subprocess to fail
            mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify error handling
            mock_exit.assert_called_once_with(1)
            assert any(
                "Error starting server" in str(call)
                for call in mock_print.call_args_list
            )

    def test_main_keyboard_interrupt(self):
        """Test main() handles KeyboardInterrupt gracefully."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("sys.exit") as mock_exit,
            patch("builtins.print") as mock_print,
        ):

            # Configure subprocess to raise KeyboardInterrupt
            mock_run.side_effect = KeyboardInterrupt()

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify graceful shutdown
            mock_exit.assert_called_once_with(0)
            assert any(
                "Server interrupted by user" in str(call)
                for call in mock_print.call_args_list
            )

    def test_main_general_exception(self):
        """Test main() handles general exceptions."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("sys.exit") as mock_exit,
            patch("builtins.print") as mock_print,
        ):

            # Configure subprocess to raise general exception
            mock_run.side_effect = RuntimeError("Something went wrong")

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify error handling
            mock_exit.assert_called_once_with(1)
            assert any(
                "Error starting server" in str(call)
                for call in mock_print.call_args_list
            )

    def test_main_subprocess_non_zero_exit(self):
        """Test main() when subprocess returns non-zero exit code."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("sys.exit") as mock_exit,
            patch("builtins.print"),
        ):

            # Configure subprocess to return non-zero exit code
            mock_run.return_value = Mock(returncode=2)

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify exit code is propagated
            mock_exit.assert_called_once_with(2)

    def test_main_prints_startup_info(self):
        """Test main() prints startup information."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("sys.exit"),
            patch("builtins.print") as mock_print,
        ):

            mock_run.return_value = Mock(returncode=0)

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify key startup messages are printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any(
                "BMC AMI DevX Code Pipeline FastMCP Server" in call
                for call in print_calls
            )
            assert any("openapi_server.py" in call for call in print_calls)
            assert any(
                "Rate limiting with token bucket algorithm" in call
                for call in print_calls
            )

    def test_path_object_usage(self):
        """Test that Path object is used correctly for file existence check."""
        with (
            patch("entrypoint.Path") as mock_path_class,
            patch("subprocess.run"),
            patch("sys.exit"),
            patch("builtins.print"),
        ):

            # Create mock Path instance
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path_class.return_value = mock_path_instance

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify Path was instantiated with correct filename
            mock_path_class.assert_called_once_with("openapi_server.py")
            mock_path_instance.exists.assert_called_once()

    def test_subprocess_call_parameters(self):
        """Test that subprocess.run is called with correct parameters."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("sys.exit"),
            patch("builtins.print"),
        ):

            mock_run.return_value = Mock(returncode=0)

            # Import and call main directly
            from entrypoint import main

            main()

            # Verify subprocess parameters
            mock_run.assert_called_once_with(
                [sys.executable, "openapi_server.py"], check=True
            )


class TestEntrypointIntegration:
    """Integration tests for entrypoint functionality."""

    def test_entrypoint_module_structure(self):
        """Test that entrypoint module has expected structure."""
        # Read the file content to verify structure
        with open("entrypoint.py", "r") as f:
            content = f.read()

        # Verify key components exist
        assert "def main():" in content
        assert 'if __name__ == "__main__":' in content
        assert "import sys" in content
        assert "from pathlib import Path" in content

    def test_main_function_docstring(self):
        """Test that main function has proper docstring."""
        with open("entrypoint.py", "r") as f:
            content = f.read()

        # Verify docstring exists
        assert '"""Main entry point for the FastMCP server."""' in content

    def test_file_structure(self):
        """Test that the entrypoint file has the expected structure."""
        with open("entrypoint.py", "r") as f:
            content = f.read()

        # Verify shebang
        lines = content.split("\n")
        assert lines[0].strip() == "#!/usr/bin/env python3"

        # Verify module docstring exists
        assert "Entry point for BMC AMI DevX" in content
        assert '"""' in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
