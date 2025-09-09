#!/bin/bash
# Coverage analysis script for BMC AMI DevX Code Pipeline FastMCP Server
# Runs comprehensive test coverage analysis and generates reports

set -e

# Configuration
PYTHON_CMD="python"
COVERAGE_DIR="htmlcov"
COVERAGE_XML="coverage.xml"
COVERAGE_THRESHOLD=80

# Check if virtual environment Python exists
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
fi

echo "📊 BMC AMI DevX Code Pipeline FastMCP Server Coverage Analysis"
echo "============================================================="
echo "🐍 Python: $PYTHON_CMD"
echo "📁 Coverage Directory: $COVERAGE_DIR"
echo "🎯 Coverage Threshold: $COVERAGE_THRESHOLD%"
echo ""

# Clean previous coverage data
echo "🧹 Cleaning previous coverage data..."
rm -rf $COVERAGE_DIR
rm -f $COVERAGE_XML
rm -f .coverage
echo "✅ Cleanup completed"
echo ""

# Run coverage analysis for each test suite
echo "🔬 Running coverage analysis..."
echo "=============================="

# Test 1: Advanced features coverage
echo "📋 Testing advanced features coverage..."
$PYTHON_CMD -m pytest test_advanced_features.py --cov=fastmcp_config --cov=openapi_server --cov-report=term-missing --cov-append -v
ADVANCED_COVERAGE_RESULT=$?

# Test 2: Elicitation coverage
echo "📋 Testing elicitation coverage..."
$PYTHON_CMD -m pytest test_elicitation.py --cov=openapi_server --cov-report=term-missing --cov-append -v
ELICITATION_COVERAGE_RESULT=$?

# Test 3: OpenAPI integration coverage
echo "📋 Testing OpenAPI integration coverage..."
$PYTHON_CMD -m pytest test_openapi_integration.py --cov=openapi_server --cov-report=term-missing --cov-append -v
OPENAPI_COVERAGE_RESULT=$?

# Test 4: Legacy tests coverage (if they exist)
echo "📋 Testing legacy coverage..."
if [ -f "test_mcp_server.py" ]; then
    $PYTHON_CMD -m pytest test_mcp_server.py --cov=main --cov-report=term-missing --cov-append -v
    LEGACY_COVERAGE_RESULT=$?
else
    echo "ℹ️  No legacy tests found, skipping"
    LEGACY_COVERAGE_RESULT=0
fi

echo "=============================="
echo ""

# Generate comprehensive coverage report
echo "📈 Generating comprehensive coverage report..."
$PYTHON_CMD -m pytest --cov=openapi_server --cov=fastmcp_config --cov=main --cov-report=html --cov-report=xml --cov-report=term-missing -v

# Check coverage threshold
echo "🎯 Checking coverage threshold..."
COVERAGE_PERCENT=$(python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('$COVERAGE_XML')
    root = tree.getroot()
    coverage = float(root.get('line-rate', 0)) * 100
    print(f'{coverage:.1f}')
except:
    print('0.0')
")

echo "📊 Overall Coverage: $COVERAGE_PERCENT%"

if (( $(echo "$COVERAGE_PERCENT >= $COVERAGE_THRESHOLD" | bc -l) )); then
    echo "✅ Coverage threshold met ($COVERAGE_PERCENT% >= $COVERAGE_THRESHOLD%)"
    COVERAGE_RESULT=0
else
    echo "❌ Coverage threshold not met ($COVERAGE_PERCENT% < $COVERAGE_THRESHOLD%)"
    COVERAGE_RESULT=1
fi

echo ""

# Show detailed coverage by file
echo "📋 Detailed Coverage by File:"
echo "-----------------------------"
$PYTHON_CMD -m coverage report --show-missing

echo ""

# Show coverage summary
echo "📊 Coverage Summary:"
echo "-------------------"
echo "  Advanced Features: $([ $ADVANCED_COVERAGE_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Elicitation Tests: $([ $ELICITATION_COVERAGE_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  OpenAPI Integration: $([ $OPENAPI_COVERAGE_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Legacy Tests: $([ $LEGACY_COVERAGE_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Overall Coverage: $([ $COVERAGE_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"

echo ""

# Generate coverage report information
if [ -d "$COVERAGE_DIR" ]; then
    echo "📁 Coverage reports generated:"
    echo "  HTML Report: $COVERAGE_DIR/index.html"
    echo "  XML Report:  $COVERAGE_XML"
    echo ""
    echo "🌐 Open HTML report: open $COVERAGE_DIR/index.html"
fi

# Final result
if [ $COVERAGE_RESULT -eq 0 ]; then
    echo "🎉 Coverage analysis completed successfully!"
    echo "📊 All tests passed with adequate coverage"
else
    echo "💥 Coverage analysis failed!"
    echo "🔧 Consider adding more tests to improve coverage"
fi

exit $COVERAGE_RESULT
