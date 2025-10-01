#!/usr/bin/env python3
"""
Generic entry point for BMC AMI DevX Code Pipeline FastMCP Server
Supports both simplified and complex implementations based on environment variables
"""

import os
import sys
from pathlib import Path

def main():
    """Main entry point that selects implementation based on environment variables."""
    
    # Get implementation choice from environment (simplified by default for new deployments)
    implementation = os.getenv("FASTMCP_IMPLEMENTATION", "simplified").lower()
    
    if implementation in ["simplified", "simple"]:
        server_file = "openapi_server_simplified.py"
        implementation_name = "Simplified Implementation (Recommended)"
    elif implementation in ["complex", "production"]:
        server_file = "openapi_server.py"
        implementation_name = "Complex Implementation (Production)"
    elif implementation == "legacy":
        server_file = "main.py"
        implementation_name = "Legacy Implementation"
    else:
        print(f"❌ Error: Invalid FASTMCP_IMPLEMENTATION: {implementation}")
        print("Valid options: simplified (default), complex, legacy")
        sys.exit(1)
    
    # Check if the server file exists
    if not Path(server_file).exists():
        print(f"❌ Error: {server_file} not found")
        print(f"Attempted implementation: {implementation_name}")
        sys.exit(1)
    
    print("🚀 BMC AMI DevX Code Pipeline FastMCP Server")
    print("=" * 50)
    print(f"🏗️  Implementation: {implementation_name}")
    print(f"📁 Server File: {server_file}")
    print("=" * 50)
    
    # Execute the selected implementation
    try:
        if implementation == "legacy":
            # Import and run legacy main.py directly
            import main
            import asyncio
            asyncio.run(main.main())
        else:
            # Execute the server file as a module
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
