#!/bin/bash

# CI/CD Setup Script for Demand Forecasting Project
# This script sets up the development environment with all CI/CD tools

set -e  # Exit on any error

echo "🚀 Setting up CI/CD environment for Demand Forecasting Project..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src" ]; then
    echo "❌ Error: Please run this script from the app-ml directory"
    exit 1
fi

# Install the project with dev dependencies
echo "📦 Installing project dependencies..."
pip install -e ".[dev]"

# Install additional CI/CD tools
echo "🔧 Installing additional CI/CD tools..."
pip install safety trivy

# Set up pre-commit hooks
echo "🪝 Setting up pre-commit hooks..."
pre-commit install
pre-commit install --hook-type commit-msg

# Create necessary directories for CI artifacts
echo "📁 Creating CI artifact directories..."
mkdir -p .github/workflows
mkdir -p test_reports
mkdir -p coverage_reports

# Set up git hooks directory if it doesn't exist
if [ ! -d ".git/hooks" ]; then
    echo "⚠️  Warning: Not a git repository. Skipping git hooks setup."
else
    echo "✅ Git hooks directory found"
fi

# Verify tools are working
echo "🔍 Verifying CI/CD tools..."

echo "  - Checking Ruff..."
ruff --version

echo "  - Checking MyPy..."
mypy --version

echo "  - Checking Bandit..."
bandit --version

echo "  - Checking Safety..."
safety --version

echo "  - Checking Pre-commit..."
pre-commit --version

# Run initial pre-commit check on all files
echo "🧪 Running initial pre-commit check..."
echo "This may take a few minutes as it checks all files..."

# Run pre-commit on all files to ensure everything is clean
pre-commit run --all-files || {
    echo "⚠️  Pre-commit found some issues. Please fix them before committing."
    echo "You can run 'pre-commit run --all-files' again to recheck."
    exit 1
}

echo "✅ CI/CD setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Make changes to your code"
echo "2. Run 'pre-commit run' to check your changes before committing"
echo "3. Commit your changes - pre-commit will automatically run checks"
echo "4. Push to GitHub - CI/CD pipeline will automatically run"
echo ""
echo "🔗 CI/CD Pipeline includes:"
echo "  - Code quality checks (Ruff, MyPy, Bandit)"
echo "  - Security scanning (Safety, Trivy)"
echo "  - Unit tests with coverage"
echo "  - Integration tests"
echo "  - Docker image validation"
echo ""
echo "📖 For more information, see .github/workflows/ci.yml"
