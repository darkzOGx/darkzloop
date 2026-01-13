# ============================================================================
# Darkzloop Makefile
# ============================================================================

.PHONY: install dev test lint format build publish clean demo help

# Default Python
PYTHON := python3

# ============================================================================
# Development
# ============================================================================

install: ## Install package in editable mode
	$(PYTHON) -m pip install -e .

dev: ## Install with dev dependencies
	$(PYTHON) -m pip install -e ".[dev]"

all: ## Install with all optional dependencies
	$(PYTHON) -m pip install -e ".[all,dev]"

# ============================================================================
# Quality
# ============================================================================

test: ## Run tests
	pytest tests/ -v

lint: ## Run linters
	ruff check darkzloop/
	mypy darkzloop/

format: ## Format code
	black darkzloop/
	ruff check darkzloop/ --fix

# ============================================================================
# Build & Publish
# ============================================================================

build: clean ## Build distribution packages
	$(PYTHON) -m pip install build
	$(PYTHON) -m build

publish: build ## Publish to PyPI
	$(PYTHON) -m pip install twine
	twine upload dist/*

publish-test: build ## Publish to TestPyPI
	$(PYTHON) -m pip install twine
	twine upload --repository testpypi dist/*

# ============================================================================
# Verification
# ============================================================================

verify: ## Run install verification script
	./test_install.sh

doctor: ## Run darkzloop doctor
	darkzloop doctor

# ============================================================================
# Demo
# ============================================================================

demo: ## Generate demo GIF (requires vhs)
	@command -v vhs >/dev/null 2>&1 || { echo "Install vhs: https://github.com/charmbracelet/vhs"; exit 1; }
	vhs demo.tape

# ============================================================================
# Cleanup
# ============================================================================

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ============================================================================
# Help
# ============================================================================

help: ## Show this help
	@echo "Darkzloop Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
