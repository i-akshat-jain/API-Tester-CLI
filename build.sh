#!/bin/bash
# Build script for API Tester CLI

set -e

echo "🔨 Building API Tester CLI..."

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info

# Install build dependencies
echo "Installing build dependencies..."
pip install -q --upgrade pip setuptools wheel build

# Build distribution
echo "Building distribution..."
python setup.py sdist bdist_wheel

# Check the build
echo "✅ Build complete!"
echo ""
echo "Distribution files:"
ls -lh dist/
echo ""
echo "To test installation:"
echo "  pip install dist/apitest-cli-1.0.0.tar.gz"
echo ""
echo "To upload to PyPI (when ready):"
echo "  pip install twine"
echo "  twine upload dist/*"

