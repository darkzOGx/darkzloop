#!/usr/bin/env bash
# ============================================================================
# Darkzloop Installation Verification Script
# ============================================================================
# This script verifies that darkzloop installs correctly and all entry points
# work on a fresh machine.
#
# Usage:
#   ./test_install.sh           # Test from local build
#   ./test_install.sh --pypi    # Test from PyPI (after publishing)
#
# Requirements:
#   - Python 3.10+
#   - pip
#   - venv module
# ============================================================================

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_test() {
    echo -e "${YELLOW}▶ Testing:${NC} $1"
}

print_pass() {
    echo -e "${GREEN}  ✓ PASS:${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}  ✗ FAIL:${NC} $1"
    ((FAILED++))
}

print_info() {
    echo -e "${BLUE}  ℹ INFO:${NC} $1"
}

cleanup() {
    if [ -d "$VENV_DIR" ]; then
        print_info "Cleaning up virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    if [ -d "$TEST_PROJECT" ]; then
        rm -rf "$TEST_PROJECT"
    fi
}

# Trap to cleanup on exit
trap cleanup EXIT

# ============================================================================
# Parse Arguments
# ============================================================================

FROM_PYPI=false
if [ "$1" == "--pypi" ]; then
    FROM_PYPI=true
fi

# ============================================================================
# Setup
# ============================================================================

print_header "Darkzloop Installation Verification"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$(mktemp -d)/darkzloop-test-venv"
TEST_PROJECT="$(mktemp -d)/test-rust-project"

echo "Script directory: $SCRIPT_DIR"
echo "Virtual env: $VENV_DIR"
echo "Test project: $TEST_PROJECT"
echo "Install from: $([ "$FROM_PYPI" = true ] && echo "PyPI" || echo "Local build")"

# ============================================================================
# Test 1: Python Version
# ============================================================================

print_header "Test 1: Python Version Check"

print_test "Python 3.10+ available"
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
    print_pass "Python $PYTHON_VERSION"
else
    print_fail "Python $PYTHON_VERSION (need 3.10+)"
    exit 1
fi

# ============================================================================
# Test 2: Create Virtual Environment
# ============================================================================

print_header "Test 2: Virtual Environment"

print_test "Creating virtual environment"
python3 -m venv "$VENV_DIR"
if [ -f "$VENV_DIR/bin/activate" ]; then
    print_pass "Virtual environment created"
else
    print_fail "Failed to create virtual environment"
    exit 1
fi

# Activate venv
source "$VENV_DIR/bin/activate"
print_info "Activated: $VIRTUAL_ENV"

# Upgrade pip
pip install --upgrade pip --quiet

# ============================================================================
# Test 3: Install Darkzloop
# ============================================================================

print_header "Test 3: Package Installation"

print_test "Installing darkzloop"
if [ "$FROM_PYPI" = true ]; then
    pip install darkzloop --quiet
else
    # Build and install from local
    cd "$SCRIPT_DIR"
    pip install build --quiet
    python -m build --quiet 2>/dev/null || true
    pip install dist/*.whl --quiet 2>/dev/null || pip install . --quiet
fi

if pip show darkzloop > /dev/null 2>&1; then
    VERSION=$(pip show darkzloop | grep Version | cut -d' ' -f2)
    print_pass "Installed darkzloop v$VERSION"
else
    print_fail "Package not installed"
    exit 1
fi

# ============================================================================
# Test 4: Entry Point
# ============================================================================

print_header "Test 4: CLI Entry Point"

print_test "darkzloop command available"
if command -v darkzloop > /dev/null 2>&1; then
    print_pass "darkzloop command found"
else
    print_fail "darkzloop command not found in PATH"
    exit 1
fi

print_test "darkzloop --help"
if darkzloop --help > /dev/null 2>&1; then
    print_pass "--help works"
else
    print_fail "--help failed"
fi

print_test "darkzloop --version (via Python)"
if python -c "from darkzloop import __version__; print(__version__)" > /dev/null 2>&1; then
    VERSION=$(python -c "from darkzloop import __version__; print(__version__)")
    print_pass "Version: $VERSION"
else
    print_fail "Cannot import version"
fi

# ============================================================================
# Test 5: All Commands Available
# ============================================================================

print_header "Test 5: Command Availability"

COMMANDS=("init" "plan" "run" "fix" "status" "graph" "config" "doctor")

for cmd in "${COMMANDS[@]}"; do
    print_test "darkzloop $cmd --help"
    if darkzloop "$cmd" --help > /dev/null 2>&1; then
        print_pass "$cmd command available"
    else
        print_fail "$cmd command failed"
    fi
done

# ============================================================================
# Test 6: Core Module Imports
# ============================================================================

print_header "Test 6: Core Module Imports"

print_test "Import darkzloop.core.fsm"
if python -c "from darkzloop.core.fsm import LoopState, FSMContext" 2>/dev/null; then
    print_pass "FSM module"
else
    print_fail "FSM module import failed"
fi

print_test "Import darkzloop.core.manifest"
if python -c "from darkzloop.core.manifest import ContextManifest" 2>/dev/null; then
    print_pass "Manifest module"
else
    print_fail "Manifest module import failed"
fi

print_test "Import darkzloop.core.semantic"
if python -c "from darkzloop.core.semantic import SemanticExpander" 2>/dev/null; then
    print_pass "Semantic module"
else
    print_fail "Semantic module import failed"
fi

print_test "Import darkzloop.core.executors"
if python -c "from darkzloop.core.executors import create_executor, ExecutorConfig" 2>/dev/null; then
    print_pass "Executors module"
else
    print_fail "Executors module import failed"
fi

# ============================================================================
# Test 7: Doctor Command (No Project)
# ============================================================================

print_header "Test 7: Doctor Command"

print_test "darkzloop doctor (outside project)"
# Doctor should run but report no project
cd /tmp
DOCTOR_OUTPUT=$(darkzloop doctor 2>&1 || true)
if echo "$DOCTOR_OUTPUT" | grep -q "Executor Configuration\|Mode:\|Command:"; then
    print_pass "Doctor shows executor info"
else
    print_info "Doctor output: $DOCTOR_OUTPUT"
    print_fail "Doctor command incomplete"
fi

# ============================================================================
# Test 8: Init in Test Project
# ============================================================================

print_header "Test 8: Project Initialization"

# Create a fake Rust project
mkdir -p "$TEST_PROJECT/src"
echo '[package]
name = "test-api"
version = "0.1.0"
edition = "2021"' > "$TEST_PROJECT/Cargo.toml"
echo 'fn main() { println!("Hello"); }' > "$TEST_PROJECT/src/main.rs"

cd "$TEST_PROJECT"

print_test "darkzloop init (Rust project)"
INIT_OUTPUT=$(darkzloop init --yes 2>&1 || true)
if [ -f "darkzloop.json" ]; then
    print_pass "Created darkzloop.json"
else
    print_info "Init output: $INIT_OUTPUT"
    print_fail "darkzloop.json not created"
fi

if [ -f "DARKZLOOP_SPEC.md" ]; then
    print_pass "Created DARKZLOOP_SPEC.md"
else
    print_fail "DARKZLOOP_SPEC.md not created"
fi

if [ -d ".darkzloop" ]; then
    print_pass "Created .darkzloop/ directory"
else
    print_fail ".darkzloop/ not created"
fi

# ============================================================================
# Test 9: Config Commands
# ============================================================================

print_header "Test 9: Config Commands"

print_test "darkzloop config show"
if darkzloop config show > /dev/null 2>&1; then
    print_pass "config show works"
else
    print_fail "config show failed"
fi

# ============================================================================
# Test 10: Semantic Expansion
# ============================================================================

print_header "Test 10: Semantic Expansion"

print_test "Expand 'billing' term"
EXPANSION=$(python -c "
from pathlib import Path
from darkzloop.core.semantic import SemanticExpander
exp = SemanticExpander(Path('.'))
result = exp.expand('billing')
print(','.join(list(result.keys())[:5]))
" 2>/dev/null)

if echo "$EXPANSION" | grep -q "billing"; then
    print_pass "Expansion includes original term"
else
    print_fail "Expansion failed"
fi

if echo "$EXPANSION" | grep -q "invoice\|payment"; then
    print_pass "Expansion includes synonyms: $EXPANSION"
else
    print_fail "No synonyms found"
fi

# ============================================================================
# Summary
# ============================================================================

print_header "Test Summary"

TOTAL=$((PASSED + FAILED))
echo ""
echo -e "  ${GREEN}Passed:${NC} $PASSED"
echo -e "  ${RED}Failed:${NC} $FAILED"
echo -e "  Total:  $TOTAL"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✓ ALL TESTS PASSED - Ready to publish!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  ✗ SOME TESTS FAILED - Fix before publishing${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 1
fi
