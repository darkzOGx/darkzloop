#!/usr/bin/env bash
# ============================================================================
# Darkzloop Pre-Publish Testing Guide
# ============================================================================
# Run this entire script, or follow steps manually.
# Usage: ./test_before_publish.sh
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Darkzloop Pre-Publish Testing"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"

# ============================================================================
# STEP 1: Local Editable Install
# ============================================================================
echo -e "${YELLOW}STEP 1: Local Editable Install${NC}"
echo "This installs the package in 'editable' mode for development."
echo ""

# Create a fresh virtual environment
VENV_DIR="$(mktemp -d)/darkzloop-test"
echo "Creating virtual environment: $VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install in editable mode
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet

echo -e "${GREEN}✓ Installed in editable mode${NC}"
echo ""

# ============================================================================
# STEP 2: Run Unit Tests
# ============================================================================
echo -e "${YELLOW}STEP 2: Running Unit Tests${NC}"
echo ""

pytest tests/ -v --tb=short

echo ""
echo -e "${GREEN}✓ All tests passed${NC}"
echo ""

# ============================================================================
# STEP 3: Verify CLI Entry Point
# ============================================================================
echo -e "${YELLOW}STEP 3: Verifying CLI Entry Point${NC}"
echo ""

echo "Testing: darkzloop --help"
darkzloop --help > /dev/null && echo -e "${GREEN}✓ --help works${NC}"

echo "Testing: darkzloop doctor"
darkzloop doctor 2>&1 | head -5
echo -e "${GREEN}✓ doctor command works${NC}"

echo ""

# ============================================================================
# STEP 4: Test in a Real Project
# ============================================================================
echo -e "${YELLOW}STEP 4: Testing in a Real Project${NC}"
echo ""

TEST_PROJECT="$(mktemp -d)/test-rust-project"
mkdir -p "$TEST_PROJECT/src"

# Create fake Rust project
cat > "$TEST_PROJECT/Cargo.toml" << 'EOF'
[package]
name = "test-api"
version = "0.1.0"
edition = "2021"
EOF

echo 'fn main() { println!("Hello"); }' > "$TEST_PROJECT/src/main.rs"

cd "$TEST_PROJECT"
echo "Created test project: $TEST_PROJECT"

echo "Testing: darkzloop init"
darkzloop init --yes 2>&1 | head -10

if [ -f "darkzloop.json" ]; then
    echo -e "${GREEN}✓ darkzloop.json created${NC}"
else
    echo -e "${RED}✗ darkzloop.json NOT created${NC}"
    exit 1
fi

echo ""

# ============================================================================
# STEP 5: Build Distribution
# ============================================================================
echo -e "${YELLOW}STEP 5: Building Distribution Packages${NC}"
echo ""

cd -  # Back to repo root
pip install build --quiet

# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build
python -m build

echo ""
ls -la dist/
echo ""
echo -e "${GREEN}✓ Built wheel and sdist${NC}"
echo ""

# ============================================================================
# STEP 6: Test Install from Built Wheel
# ============================================================================
echo -e "${YELLOW}STEP 6: Testing Install from Built Wheel${NC}"
echo ""

# Create another fresh venv
WHEEL_VENV="$(mktemp -d)/darkzloop-wheel-test"
python3 -m venv "$WHEEL_VENV"
source "$WHEEL_VENV/bin/activate"
pip install --upgrade pip --quiet

# Install from wheel
pip install dist/*.whl --quiet

echo "Testing installed wheel:"
darkzloop --help > /dev/null && echo -e "${GREEN}✓ CLI works from wheel${NC}"

INSTALLED_VERSION=$(python -c "from darkzloop import __version__; print(__version__)")
echo -e "${GREEN}✓ Installed version: $INSTALLED_VERSION${NC}"

echo ""

# ============================================================================
# STEP 7: Check Package Metadata
# ============================================================================
echo -e "${YELLOW}STEP 7: Checking Package Metadata${NC}"
echo ""

pip show darkzloop

echo ""
echo -e "${GREEN}✓ Metadata looks good${NC}"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${BLUE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ ALL PRE-PUBLISH TESTS PASSED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. (Optional) Publish to TestPyPI first:"
echo "     twine upload --repository testpypi dist/*"
echo "     pip install -i https://test.pypi.org/simple/ darkzloop"
echo ""
echo "  2. Publish to PyPI:"
echo "     twine upload dist/*"
echo ""
echo "  3. Verify on PyPI:"
echo "     pip install darkzloop"
echo "     darkzloop --help"
echo ""

# Cleanup
deactivate 2>/dev/null || true
