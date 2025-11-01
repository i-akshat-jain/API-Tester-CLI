#!/bin/bash
# Installation script for API Tester CLI (editable mode)

set -e

echo "📦 Installing API Tester CLI in editable mode..."

# Upgrade pip first (fixes the "No module named pip" issue)
echo "Upgrading pip..."
python3 -m pip install --upgrade pip

# Install in editable mode
echo "Installing package..."
pip install -e .

echo "✅ Installation complete!"
echo ""
echo "You can now use 'apitest' command:"
echo "  apitest examples/simple-api.yaml"

