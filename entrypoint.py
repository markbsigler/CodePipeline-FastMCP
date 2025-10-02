#!/usr/bin/env python3
"""
Entry point for BMC AMI DevX Code Pipeline FastMCP Server
Now uses the unified FastMCP implementation with full enterprise features
"""

import sys
from pathlib import Path


def main():
    """Main entry point for the FastMCP server."""

    server_file = "openapi_server.py"
    implementation_name = "BMC AMI DevX Code Pipeline FastMCP Server"

    # Check if the server file exists
    if not Path(server_file).exists():
        print(f"❌ Error: {server_file} not found")
        print(f"Expected: {implementation_name}")
        sys.exit(1)

    print("🚀 BMC AMI DevX Code Pipeline FastMCP Server")
    print("=" * 50)
    print(f"📁 Server File: {server_file}")
    print(f"🏗️  FastMCP with Enterprise Features:")
    print("   ✅ Rate limiting with token bucket algorithm")
    print("   ✅ LRU/TTL caching with comprehensive management")
    print("   ✅ Real-time metrics and monitoring")
    print("   ✅ Error recovery with exponential backoff")
    print("   ✅ Multi-provider authentication support")
    print("=" * 50)

    # Execute the server file as a module
    try:
        import subprocess

        result = subprocess.run([sys.executable, server_file], check=True)
        sys.exit(result.returncode)

    except KeyboardInterrupt:
        print("\n🛑 Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
