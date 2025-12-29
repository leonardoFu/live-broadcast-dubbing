.PHONY: fmt lint typecheck test help setup api-status metrics clean install-hooks
.PHONY: media-dev media-down media-logs media-ps

PYTHON := python3.10
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python

# Media Service paths
MEDIA_SERVICE := apps/media-service
MEDIA_VENV := $(MEDIA_SERVICE)/venv
MEDIA_PYTHON := $(MEDIA_VENV)/bin/python

# Help target
help:
	@echo "Python Monorepo - Available Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              - Create venv and install all services"
	@echo "  make media-setup        - Setup media-service only"
	@echo ""
	@echo "Docker (Media Service):"
	@echo "  make media-dev          - Start media-service with Docker Compose"
	@echo "  make media-down         - Stop media-service Docker services"
	@echo "  make media-logs         - View media-service Docker logs"
	@echo "  make media-ps           - List media-service Docker containers"
	@echo ""
	@echo "Observability (Media Service):"
	@echo "  make api-status         - Query MediaMTX Control API for active streams"
	@echo "  make metrics            - Query Prometheus metrics endpoint"
	@echo ""
	@echo "Code Quality:"
	@echo "  make fmt                - Format code with ruff"
	@echo "  make lint               - Lint code with ruff"
	@echo "  make typecheck          - Type check with mypy"
	@echo "  make clean              - Remove build artifacts and caches"
	@echo ""
	@echo "Testing (Media Service):"
	@echo "  make media-test         - Run all media-service tests (unit + integration)"
	@echo "  make media-test-unit    - Run media-service unit tests"
	@echo "  make media-test-integration - Run media-service integration tests (requires Docker)"
	@echo "  make media-test-coverage - Run media-service tests with coverage"
	@echo ""
	@echo "STS Service:"
	@echo "  make sts-echo           - Start Echo STS Service (for E2E testing)"
	@echo "  make sts-test           - Run all sts-service tests"
	@echo "  make sts-test-unit      - Run sts-service unit tests"
	@echo "  make sts-test-integration - Run sts-service integration tests"
	@echo "  make sts-test-coverage  - Run sts-service tests with coverage"
	@echo ""
	@echo "Testing (E2E - Cross-Service):"
	@echo "  make e2e-test           - Run E2E tests spanning multiple services"
	@echo ""

# Monorepo setup target
setup:
	@echo "Setting up monorepo development environment..."
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e libs/common
	$(VENV)/bin/pip install -e libs/contracts
	$(VENV)/bin/pip install -e "apps/media-service[dev]"
	$(VENV)/bin/pip install -e "apps/sts-service[dev]"
	@echo "✓ Monorepo setup complete!"
	@echo "  Activate with: source $(VENV)/bin/activate"

# Media Service setup
media-setup:
	@echo "Setting up media-service development environment..."
	$(PYTHON) -m venv $(MEDIA_VENV)
	$(MEDIA_VENV)/bin/pip install --upgrade pip
	$(MEDIA_VENV)/bin/pip install -e libs/common
	$(MEDIA_VENV)/bin/pip install -e libs/contracts
	$(MEDIA_VENV)/bin/pip install -e "$(MEDIA_SERVICE)[dev]"
	@echo "✓ Media service setup complete!"
	@echo "  Activate with: source $(MEDIA_VENV)/bin/activate"

# =============================================================================
# Media Service Docker
# =============================================================================
media-dev:
	docker compose -f $(MEDIA_SERVICE)/docker-compose.yml up --build

media-down:
	docker compose -f $(MEDIA_SERVICE)/docker-compose.yml down --remove-orphans

media-logs:
	docker compose -f $(MEDIA_SERVICE)/docker-compose.yml logs -f --tail=200

media-ps:
	docker compose -f $(MEDIA_SERVICE)/docker-compose.yml ps

# Observability targets
api-status:
	@echo "Querying MediaMTX Control API for active streams..."
	@curl -s http://localhost:9997/v3/paths/list | python3 -m json.tool || echo "Error: MediaMTX may not be running. Try 'make dev' first."

metrics:
	@echo "Querying Prometheus metrics endpoint..."
	@curl -s http://localhost:9998/metrics || echo "Error: MediaMTX may not be running. Try 'make dev' first."

# Code quality targets
fmt:
	$(VENV_PYTHON) -m ruff format .

lint:
	$(VENV_PYTHON) -m ruff check .

typecheck:
	@PY_FILES=$$(find . -type f \( -name '*.py' -o -name '*.pyi' \) \
		-not -path './.venv/*' \
		-not -path './.codex/*' \
		-not -path './.project-scripts/*' \
		-not -path './.specify/*' \
		-not -path './.sts-service-archive/*' \
		-not -path './specs/*'); \
	if [ -z "$$PY_FILES" ]; then echo "No Python files to typecheck."; exit 0; fi; \
	$(VENV_PYTHON) -m mypy $$PY_FILES

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf coverage htmlcov .coverage
	@echo "✓ Build artifacts cleaned!"

install-hooks:
	$(VENV_PYTHON) -m pre_commit install
	@echo "✓ Pre-commit hooks installed"

# =============================================================================
# Media Service Testing
# =============================================================================
.PHONY: media-test media-test-unit media-test-integration media-test-coverage

media-test:
	$(MEDIA_PYTHON) -m pytest $(MEDIA_SERVICE)/tests/ -v

media-test-unit:
	$(MEDIA_PYTHON) -m pytest $(MEDIA_SERVICE)/tests/unit/ -v

media-test-integration:
	$(MEDIA_PYTHON) -m pytest $(MEDIA_SERVICE)/tests/integration/ -v -m integration

media-test-coverage:
	$(MEDIA_PYTHON) -m pytest $(MEDIA_SERVICE)/tests/ --cov=$(MEDIA_SERVICE)/src --cov-report=html --cov-report=term

# =============================================================================
# STS Service
# =============================================================================
STS_SERVICE := apps/sts-service

.PHONY: sts-test sts-test-unit sts-test-integration sts-test-coverage sts-echo

sts-test:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/ -v

sts-test-unit:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/unit/ -v

sts-test-integration:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/integration/ -v -m integration

sts-test-coverage:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/ --cov=sts_service --cov-report=html --cov-report=term --cov-fail-under=80

sts-echo:
	@echo "Starting Echo STS Service..."
	$(VENV_PYTHON) -m sts_service.echo

# =============================================================================
# E2E Testing (Cross-Service)
# =============================================================================
.PHONY: e2e-test

e2e-test:
	@echo "Running cross-service E2E tests (media-service + sts-service)..."
	$(VENV_PYTHON) -m pytest tests/e2e/ -v -m e2e
