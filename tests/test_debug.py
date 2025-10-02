#!/usr/bin/env python3
"""
Comprehensive tests for debug.py to achieve 100% coverage.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


class TestDebugScript:
    """Test class for debug.py script coverage."""

    def test_debug_script_execution(self):
        """Test debug script can be executed successfully."""
        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Should execute without errors
        assert result.returncode == 0
        assert "=== Debug Information ===" in result.stdout
        assert "=== Debug Complete ===" in result.stdout

    def test_debug_script_python_info(self):
        """Test debug script displays Python information."""
        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Should display Python version and executable
        assert "Python version:" in result.stdout
        assert "Python executable:" in result.stdout
        assert "Working directory:" in result.stdout
        assert "Files in working directory:" in result.stdout

    def test_debug_script_environment_variables(self):
        """Test debug script displays relevant environment variables."""
        # Set some test environment variables
        test_env = os.environ.copy()
        test_env.update(
            {
                "FASTMCP_TEST_VAR": "test_value",
                "HOST": "test_host",
                "PORT": "8080",
                "LOG_LEVEL": "DEBUG",
                "IRRELEVANT_VAR": "should_not_appear",
            }
        )

        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            env=test_env,
            cwd=Path(__file__).parent.parent,
        )

        # Should display relevant environment variables
        assert "=== Environment Variables ===" in result.stdout
        assert "FASTMCP_TEST_VAR: test_value" in result.stdout
        assert "HOST: test_host" in result.stdout
        assert "PORT: 8080" in result.stdout
        assert "LOG_LEVEL: DEBUG" in result.stdout

        # Should not display irrelevant variables
        assert "IRRELEVANT_VAR" not in result.stdout

    def test_debug_script_import_testing(self):
        """Test debug script tests imports."""
        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Should test various imports
        assert "=== Testing imports ===" in result.stdout
        assert "json imported" in result.stdout
        assert "httpx imported" in result.stdout
        assert "uvicorn imported" in result.stdout
        assert "starlette imported" in result.stdout

    def test_debug_script_main_import_testing(self):
        """Test debug script tests main.py import."""
        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Should test main.py import
        assert "=== Testing main.py ===" in result.stdout
        assert "About to import main.py..." in result.stdout
        # Should succeed or show error details
        assert (
            "main.py imported successfully" in result.stdout
            or "main.py import failed" in result.stdout
        )

    def test_debug_script_with_missing_directory(self):
        """Test debug script behavior in different directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy debug.py to temp directory
            debug_content = Path("debug.py").read_text()
            temp_debug = Path(temp_dir) / "debug.py"
            temp_debug.write_text(debug_content)

            result = subprocess.run(
                [sys.executable, str(temp_debug)],
                capture_output=True,
                text=True,
                cwd=temp_dir,
            )

            # Should still execute but may fail on main.py import
            assert result.returncode == 0
            assert "=== Debug Information ===" in result.stdout

    def test_debug_script_environment_filtering(self):
        """Test environment variable filtering logic."""
        # Test with no relevant environment variables
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if not any(x in k for x in ["FASTMCP", "HOST", "PORT", "LOG_LEVEL"])
        }

        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            env=clean_env,
            cwd=Path(__file__).parent.parent,
        )

        # Should still show environment section but with fewer variables
        assert "=== Environment Variables ===" in result.stdout
        assert result.returncode == 0

    def test_debug_script_import_error_handling(self):
        """Test debug script handles import errors gracefully."""
        # Create a modified debug script that will fail imports
        debug_content = Path("debug.py").read_text()

        # Replace import attempts with failing ones
        modified_content = debug_content.replace(
            'print("✓ json imported")',
            'import nonexistent_module; print("✓ json imported")',
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(modified_content)
            f.flush()

            try:
                result = subprocess.run(
                    [sys.executable, f.name], capture_output=True, text=True
                )

                # Should handle import errors gracefully
                assert "import failed" in result.stdout or result.returncode == 0
            finally:
                os.unlink(f.name)

    def test_debug_script_main_import_error_handling(self):
        """Test debug script handles main.py import errors."""
        # Test in directory without main.py
        with tempfile.TemporaryDirectory() as temp_dir:
            debug_content = Path("debug.py").read_text()
            temp_debug = Path(temp_dir) / "debug.py"
            temp_debug.write_text(debug_content)

            result = subprocess.run(
                [sys.executable, str(temp_debug)],
                capture_output=True,
                text=True,
                cwd=temp_dir,
            )

            # Should handle main.py import failure gracefully
            assert result.returncode == 0
            assert (
                "main.py import failed" in result.stdout
                or "main.py imported successfully" in result.stdout
            )

    def test_debug_script_output_format(self):
        """Test debug script output format and structure."""
        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        output_lines = result.stdout.split("\n")

        # Check for expected sections in order
        sections = [
            "=== Debug Information ===",
            "=== Environment Variables ===",
            "=== Testing imports ===",
            "=== Testing main.py ===",
            "=== Debug Complete ===",
        ]

        for section in sections:
            assert any(
                section in line for line in output_lines
            ), f"Missing section: {section}"

    def test_debug_script_as_module(self):
        """Test debug script can be run as a module."""
        # Test running debug.py as a module
        result = subprocess.run(
            [sys.executable, "-c", "exec(open('debug.py').read())"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Should execute successfully
        assert result.returncode == 0
        assert "=== Debug Information ===" in result.stdout

    def test_debug_script_working_directory_listing(self):
        """Test debug script lists working directory contents."""
        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Should list some expected files in the project directory
        expected_files = ["debug.py", "openapi_server.py", "requirements.txt"]

        for expected_file in expected_files:
            if Path(expected_file).exists():
                assert expected_file in result.stdout

    def test_debug_script_comprehensive_coverage(self):
        """Test debug script with comprehensive environment setup."""
        # Set up comprehensive test environment
        test_env = os.environ.copy()
        test_env.update(
            {
                "FASTMCP_SERVER_HOST": "0.0.0.0",
                "FASTMCP_SERVER_PORT": "8080",
                "FASTMCP_LOG_LEVEL": "INFO",
                "FASTMCP_CACHE_ENABLED": "true",
                "HOST": "localhost",
                "PORT": "3000",
                "LOG_LEVEL": "DEBUG",
            }
        )

        result = subprocess.run(
            [sys.executable, "debug.py"],
            capture_output=True,
            text=True,
            env=test_env,
            cwd=Path(__file__).parent.parent,
        )

        # Should execute successfully and show all relevant variables
        assert result.returncode == 0
        assert "FASTMCP_SERVER_HOST: 0.0.0.0" in result.stdout
        assert "FASTMCP_SERVER_PORT: 8080" in result.stdout
        assert "HOST: localhost" in result.stdout
        assert "PORT: 3000" in result.stdout
        assert "LOG_LEVEL: DEBUG" in result.stdout
