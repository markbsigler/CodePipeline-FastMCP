#!/usr/bin/env python3
"""
Comparison script between manual MCP implementation and OpenAPI integration.

This script demonstrates the benefits and differences between the two approaches.
"""

import json
from pathlib import Path
from typing import Any, Dict


def analyze_manual_implementation() -> Dict[str, Any]:
    """Analyze the manual MCP implementation."""
    main_py_path = Path("main.py")
    if not main_py_path.exists():
        return {"error": "main.py not found"}

    with open(main_py_path, "r") as f:
        content = main_py_path.read_text()

    # Count lines and functions
    lines = content.split("\n")
    total_lines = len(lines)

    # Count MCP tools (functions decorated with @server.tool)
    tool_functions = []
    for i, line in enumerate(lines):
        if "@server.tool" in line and i + 1 < len(lines):
            next_line = lines[i + 1]
            if "def " in next_line:
                func_name = next_line.split("def ")[1].split("(")[0]
                tool_functions.append(func_name)

    # Count BMC client methods
    bmc_methods = []
    in_class = False
    for line in lines:
        if "class BMCAMIDevXClient:" in line:
            in_class = True
            continue
        elif in_class and line.startswith("class "):
            in_class = False
            continue
        elif (
            in_class
            and line.strip().startswith("def ")
            and not line.strip().startswith("def _")
        ):
            method_name = line.strip().split("def ")[1].split("(")[0]
            bmc_methods.append(method_name)

    return {
        "total_lines": total_lines,
        "mcp_tools": tool_functions,
        "bmc_methods": bmc_methods,
        "tool_count": len(tool_functions),
        "method_count": len(bmc_methods),
    }


def analyze_openapi_implementation() -> Dict[str, Any]:
    """Analyze the OpenAPI MCP implementation."""
    openapi_py_path = Path("openapi_server.py")
    if not openapi_py_path.exists():
        return {"error": "openapi_server.py not found"}

    with open(openapi_py_path, "r") as f:
        content = openapi_py_path.read_text()

    # Count lines and functions
    lines = content.split("\n")
    total_lines = len(lines)

    # Count custom tools
    custom_tools = []
    for i, line in enumerate(lines):
        if "@server.tool" in line and i + 1 < len(lines):
            next_line = lines[i + 1]
            if "def " in next_line:
                func_name = next_line.split("def ")[1].split("(")[0]
                custom_tools.append(func_name)

    # Load OpenAPI spec to count generated tools
    openapi_spec_path = Path("config/openapi.json")
    openapi_tools = []
    if openapi_spec_path.exists():
        with open(openapi_spec_path, "r") as f:
            spec = json.load(f)

        # Count API endpoints
        for path, methods in spec.get("paths", {}).items():
            for method in methods.keys():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    # Generate tool name from path and method
                    tool_name = f"{method.lower()}_{path.replace('/', '_').replace('{', '').replace('}', '').strip('_')}"
                    openapi_tools.append(tool_name)

    return {
        "total_lines": total_lines,
        "custom_tools": custom_tools,
        "openapi_tools": openapi_tools,
        "custom_tool_count": len(custom_tools),
        "openapi_tool_count": len(openapi_tools),
        "total_tool_count": len(custom_tools) + len(openapi_tools),
    }


def compare_implementations():
    """Compare the two implementations."""
    print("🔍 BMC AMI DevX Code Pipeline MCP Server Implementation Comparison")
    print("=" * 80)

    manual = analyze_manual_implementation()
    openapi = analyze_openapi_implementation()

    if "error" in manual:
        print(f"❌ Manual implementation analysis failed: {manual['error']}")
        return

    if "error" in openapi:
        print(f"❌ OpenAPI implementation analysis failed: {openapi['error']}")
        return

    print("\n📊 Code Metrics Comparison")
    print("-" * 40)
    print(f"Manual Implementation:")
    print(f"  • Total lines of code: {manual['total_lines']:,}")
    print(f"  • MCP tools: {manual['tool_count']}")
    print(f"  • BMC client methods: {manual['method_count']}")

    print(f"\nOpenAPI Implementation:")
    print(f"  • Total lines of code: {openapi['total_lines']:,}")
    print(f"  • Custom tools: {openapi['custom_tool_count']}")
    print(f"  • Generated tools: {openapi['openapi_tool_count']}")
    print(f"  • Total tools: {openapi['total_tool_count']}")

    print(f"\n📈 Improvement Metrics")
    print("-" * 40)
    line_reduction = manual["total_lines"] - openapi["total_lines"]
    line_reduction_pct = (line_reduction / manual["total_lines"]) * 100
    tool_increase = openapi["total_tool_count"] - manual["tool_count"]
    tool_increase_pct = (tool_increase / manual["tool_count"]) * 100

    print(f"  • Code reduction: {line_reduction:,} lines ({line_reduction_pct:.1f}%)")
    print(f"  • Tool increase: +{tool_increase} tools ({tool_increase_pct:.1f}%)")
    print(
        f"  • Efficiency ratio: {openapi['total_tool_count'] / openapi['total_lines']:.2f} tools/line"
    )

    print(f"\n🛠️ Manual Implementation Tools")
    print("-" * 40)
    for tool in manual["mcp_tools"]:
        print(f"  • {tool}")

    print(f"\n🔧 OpenAPI Implementation Custom Tools")
    print("-" * 40)
    for tool in openapi["custom_tools"]:
        print(f"  • {tool}")

    print(f"\n🤖 OpenAPI Generated Tools (Sample)")
    print("-" * 40)
    for tool in openapi["openapi_tools"][:10]:  # Show first 10
        print(f"  • {tool}")
    if len(openapi["openapi_tools"]) > 10:
        print(f"  • ... and {len(openapi['openapi_tools']) - 10} more")

    print(f"\n✅ Benefits of OpenAPI Integration")
    print("-" * 40)
    print("  • 🚀 Automatic tool generation from API specification")
    print("  • 📝 Always in sync with BMC API changes")
    print("  • 🔧 Reduced maintenance overhead")
    print("  • 📚 Complete API coverage")
    print("  • 🎯 Type-safe parameter validation")
    print("  • 📖 Self-documenting through OpenAPI spec")
    print("  • 🔄 Easy to update when API evolves")
    print("  • 🧪 Consistent error handling across all tools")
    print("  • ⚡ Better performance with connection pooling")
    print("  • 📊 Built-in monitoring and metrics")

    print(f"\n⚠️ Considerations")
    print("-" * 40)
    print("  • 🔍 Less control over individual tool behavior")
    print("  • 📋 Dependent on OpenAPI specification quality")
    print("  • 🎨 Limited customization of tool descriptions")
    print("  • 🔧 May require OpenAPI spec updates for new features")

    print(f"\n🎯 Recommendation")
    print("-" * 40)
    print("The OpenAPI integration approach is recommended for:")
    print("  • Production environments requiring complete API coverage")
    print("  • Teams that want to minimize maintenance overhead")
    print("  • Projects where API stability is important")
    print("  • Organizations with well-maintained OpenAPI specifications")

    print("\n" + "=" * 80)


def show_api_coverage():
    """Show API coverage comparison."""
    print("\n📋 API Coverage Analysis")
    print("=" * 50)

    # Load OpenAPI spec
    openapi_spec_path = Path("config/openapi.json")
    if not openapi_spec_path.exists():
        print("❌ OpenAPI specification not found")
        return

    with open(openapi_spec_path, "r") as f:
        spec = json.load(f)

    # Analyze API endpoints
    endpoints = []
    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                endpoints.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", "No summary"),
                        "tags": details.get("tags", []),
                    }
                )

    # Group by tags
    by_tag = {}
    for endpoint in endpoints:
        for tag in endpoint["tags"]:
            if tag not in by_tag:
                by_tag[tag] = []
            by_tag[tag].append(endpoint)

    print(f"Total API endpoints: {len(endpoints)}")
    print(f"API categories: {len(by_tag)}")

    for tag, tag_endpoints in by_tag.items():
        print(f"\n📁 {tag} ({len(tag_endpoints)} endpoints)")
        for endpoint in tag_endpoints:
            print(
                f"  • {endpoint['method']} {endpoint['path']} - {endpoint['summary']}"
            )


if __name__ == "__main__":
    compare_implementations()
    show_api_coverage()
