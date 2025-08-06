#!/bin/bash
# Comprehensive setup script for BMC AMI DevX Code Pipeline MCP Server
# Sets up Python environment, dependencies, configuration, and development tools

set -e

echo "🚀 Setting up BMC AMI DevX Code Pipeline MCP Server"
echo "=================================================="

# Check Python version
echo "🐍 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION+ required, found $PYTHON_VERSION"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip and core tools
echo "⬆️  Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel

# Install project dependencies
echo "📚 Installing project dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Dependencies installed from requirements.txt"
else
    echo "❌ requirements.txt not found"
    exit 1
fi

# Setup configuration files
echo "⚙️  Setting up configuration files..."

# Copy environment template if it doesn't exist
if [ -f "config/.env.example" ] && [ ! -f "config/.env" ]; then
    cp config/.env.example config/.env
    echo "✅ Environment file created from template"
    echo "📝 Please edit config/.env with your settings"
else
    echo "ℹ️  Environment file already exists or template not found"
fi

# Verify OpenAPI specification exists
if [ -f "config/openapi.json" ]; then
    echo "✅ OpenAPI specification found"
else
    echo "⚠️  OpenAPI specification not found at config/openapi.json"
    if [ -f "config/openapi.example.json" ]; then
        cp config/openapi.example.json config/openapi.json
        echo "✅ Created from example template"
    fi
fi

# Install development tools
echo "🔧 Setting up development tools..."

# Install pre-commit hooks
if command -v pre-commit >/dev/null 2>&1; then
    pre-commit install
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  pre-commit not available, skipping hook installation"
fi

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p logs
mkdir -p htmlcov
echo "✅ Project directories created"

# Verify installation
echo "🧪 Verifying installation..."

# Test import of main module
if .venv/bin/python -c "import main; print('✅ Main module imports successfully')" 2>/dev/null; then
    echo "✅ Core module verification passed"
else
    echo "❌ Core module verification failed"
    exit 1
fi

# Test dependencies
echo "📋 Testing key dependencies..."
.venv/bin/python -c "
import starlette
import uvicorn
import httpx
import pytest
print('✅ All key dependencies available')
"

echo "=================================================="
echo "🎉 Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "  1. Activate virtual environment: source .venv/bin/activate"
echo "  2. Edit configuration: nano config/.env"
echo "  3. Run development server: npm run dev"
echo "  4. Run tests: npm run test"
echo "  5. Check health: curl http://localhost:8000/health"
echo ""
echo "📚 Available commands:"
echo "  npm run dev              # Start development server"
echo "  npm run test             # Run test suite"
echo "  npm run test:coverage    # Run tests with coverage"
echo "  npm run lint:fix         # Fix code formatting"
echo "  npm run docker:build     # Build Docker image"
echo ""
echo "🔗 Documentation:"
echo "  README.md                # Project overview and API reference"
echo "  PROMPT.md                # Technical implementation guide"
echo "  config/.env              # Environment configuration"
