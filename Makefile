.PHONY: dev down logs ps fmt lint typecheck test help setup-stream setup-sts api-status metrics

PYTHON := python3.10
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python

# Help target
help:
	@echo "Python Monorepo - Available Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make setup           - Create venv and install all services"
	@echo ""
	@echo "Docker:"
	@echo "  make dev             - Start services with Docker Compose"
	@echo "  make down            - Stop Docker services"
	@echo "  make logs            - View Docker logs"
	@echo "  make ps              - List Docker containers"
	@echo ""
	@echo "Observability:"
	@echo "  make api-status      - Query MediaMTX Control API for active streams"
	@echo "  make metrics         - Query Prometheus metrics endpoint"
	@echo ""
	@echo "Code Quality:"
	@echo "  make fmt             - Format code with ruff"
	@echo "  make lint            - Lint code with ruff"
	@echo "  make typecheck       - Type check with mypy"
	@echo "  make clean           - Remove build artifacts and caches"
	@echo ""
	@echo "Testing:"
	@echo "  make test            - Run all tests"
	@echo "  make test-unit       - Run unit tests only"
	@echo "  make test-contract   - Run contract tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-coverage   - Run tests with coverage report"
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

dev:
	docker compose -f deploy/docker-compose.yml up --build

down:
	docker compose -f deploy/docker-compose.yml down --remove-orphans

logs:
	docker compose -f deploy/docker-compose.yml logs -f --tail=200

ps:
	docker compose -f deploy/docker-compose.yml ps

# Observability targets (T070, T071)
api-status:
	@echo "Querying MediaMTX Control API for active streams..."
	@curl -s -u admin:admin http://localhost:9997/v3/paths/list | python3 -m json.tool || echo "Error: MediaMTX may not be running. Try 'make dev' first."

metrics:
	@echo "Querying Prometheus metrics endpoint..."
	@curl -s -u admin:admin http://localhost:9998/metrics || echo "Error: MediaMTX may not be running. Try 'make dev' first."

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

test:
	$(VENV_PYTHON) -m pytest -q

# TDD workflow commands
.PHONY: test-unit test-contract test-integration test-all test-coverage test-watch pre-implement install-hooks clean

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

test-unit:
	$(VENV_PYTHON) -m pytest apps/ tests/ -m unit -v

test-contract:
	$(VENV_PYTHON) -m pytest apps/ tests/ -m contract -v

test-integration:
	$(VENV_PYTHON) -m pytest apps/ tests/ -m integration -v

test-all:
	$(VENV_PYTHON) -m pytest apps/ tests/ -v

test-coverage:
	$(VENV_PYTHON) -m pytest apps/ tests/ --cov=apps --cov-report=html --cov-report=term

test-watch:
	$(VENV_PYTHON) -m pytest apps/ tests/ -f -v

pre-implement:
	$(VENV_PYTHON) .specify/scripts/pre_implement_check.py

install-hooks:
	$(VENV_PYTHON) -m pre_commit install
	@echo "✓ Pre-commit hooks installed"
