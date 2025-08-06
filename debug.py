#!/usr/bin/env python3
"""Debug script to test container environment"""

import os
import sys

print("=== Debug Information ===")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Working directory: {os.getcwd()}")
print(f"Files in working directory: {os.listdir('.')}")

print("\n=== Environment Variables ===")
for key, value in sorted(os.environ.items()):
    if "FASTMCP" in key or key in ["HOST", "PORT", "LOG_LEVEL"]:
        print(f"{key}: {value}")

print("\n=== Testing imports ===")
try:
    print("✓ json imported")
except Exception as e:
    print(f"✗ json import failed: {e}")

try:
    print("✓ httpx imported")
except Exception as e:
    print(f"✗ httpx import failed: {e}")

try:
    print("✓ uvicorn imported")
except Exception as e:
    print(f"✗ uvicorn import failed: {e}")

try:
    print("✓ starlette imported")
except Exception as e:
    print(f"✗ starlette import failed: {e}")

print("\n=== Testing main.py ===")
try:
    print("About to import main.py...")
    print("✓ main.py imported successfully")
except Exception as e:
    import traceback

    print(f"✗ main.py import failed: {e}")
    traceback.print_exc()

print("\n=== Debug Complete ===")
