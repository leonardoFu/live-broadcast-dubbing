.PHONY: fmt lint typecheck test help setup api-status metrics clean clean-artifacts install-hooks
.PHONY: media-dev media-down media-logs media-ps
.PHONY: e2e-test e2e-test-p1 e2e-clean e2e-logs e2e-media-up e2e-media-down e2e-sts-up e2e-sts-down
.PHONY: sts-docker sts-docker-stop sts-docker-logs sts-docker-status
.PHONY: sts-elevenlabs sts-elevenlabs-stop sts-elevenlabs-logs
.PHONY: dev-up dev-down dev-logs dev-ps dev-test dev-push dev-play dev-play-in
.PHONY: dev-up-light dev-down-light

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
	@echo "  make clean-artifacts    - Remove debug artifacts (.artifacts/)"
	@echo ""
	@echo "Testing (Media Service):"
	@echo "  make media-test         - Run all media-service tests (unit + integration)"
	@echo "  make media-test-unit    - Run media-service unit tests"
	@echo "  make media-test-integration - Run media-service integration tests (requires Docker)"
	@echo "  make media-test-coverage - Run media-service tests with coverage"
	@echo ""
	@echo "STS Service (Native Python):"
	@echo "  make sts-full           - Start Full STS Service (ASR+Translation+TTS) on port 8003"
	@echo "  make sts-full-stop      - Stop Full STS Service"
	@echo "  make sts-full-logs      - View Full STS Service logs in real-time"
	@echo "  make sts-full-status    - Check Full STS Service status"
	@echo "  make sts-echo           - Start Echo STS Service (for E2E testing)"
	@echo "  make sts-test           - Run all sts-service tests"
	@echo "  make sts-test-unit      - Run sts-service unit tests"
	@echo "  make sts-test-e2e       - Run sts-service E2E tests"
	@echo "  make sts-test-coverage  - Run sts-service tests with coverage"
	@echo ""
	@echo "STS Service (Docker - Full with Coqui TTS):"
	@echo "  make sts-docker         - Start Full STS Service in Docker (port 8000)"
	@echo "  make sts-docker-stop    - Stop Full STS Docker container"
	@echo "  make sts-docker-logs    - View Full STS Docker logs"
	@echo "  make sts-docker-status  - Check Full STS Docker status"
	@echo ""
	@echo "STS Service (Docker - Lightweight with ElevenLabs):"
	@echo "  make sts-elevenlabs     - Start ElevenLabs STS (faster build, smaller image)"
	@echo "  make sts-elevenlabs-stop- Stop ElevenLabs STS container"
	@echo "  make sts-elevenlabs-logs- View ElevenLabs STS logs"
	@echo ""
	@echo "Integrated Development (Media + STS Docker):"
	@echo "  make dev-up             - Start media-service + Full STS Docker"
	@echo "  make dev-up-light       - Start media-service + ElevenLabs STS (recommended)"
	@echo "  make dev-down           - Stop all development services"
	@echo "  make dev-logs           - View logs from all services"
	@echo "  make dev-ps             - List all running containers"
	@echo "  make dev-test           - Publish test fixture and monitor"
	@echo "  make dev-push           - Push speech.mp4 test stream (loops forever)"
	@echo "  make dev-play           - Play dubbed output stream with ffplay"
	@echo "  make dev-play-in        - Play input stream with ffplay (for comparison)"
	@echo ""
	@echo "Testing (E2E - Cross-Service):"
	@echo "  make e2e-test           - Run E2E tests (auto-starts services via pytest)"
	@echo "  make e2e-test-p1        - Run P1 E2E tests (full pipeline, real STS)"
	@echo "  make e2e-logs           - View logs from both service environments"
	@echo "  make e2e-clean          - Stop and cleanup all E2E Docker resources"
	@echo ""
	@echo "E2E Manual Service Control (for debugging):"
	@echo "  make e2e-media-up       - Start media-service environment (MediaMTX + media-service)"
	@echo "  make e2e-media-down     - Stop media-service environment"
	@echo "  make e2e-sts-up         - Start STS-service environment"
	@echo "  make e2e-sts-down       - Stop STS-service environment"
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

clean-artifacts:
	@echo "Cleaning debug artifacts..."
	rm -rf .artifacts/
	@echo "✓ Debug artifacts cleaned!"

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

.PHONY: sts-test sts-test-unit sts-test-e2e sts-test-coverage sts-echo sts-full sts-full-stop sts-full-logs sts-full-status

sts-test:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/ -v

sts-test-unit:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/unit/ -v

sts-test-e2e:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/e2e/ -v -m e2e

sts-test-coverage:
	$(VENV_PYTHON) -m pytest $(STS_SERVICE)/tests/ --cov=sts_service --cov-report=html --cov-report=term --cov-fail-under=80

sts-echo:
	@echo "Starting Echo STS Service..."
	$(VENV_PYTHON) -m sts_service.echo

# Full STS Service (ASR + Translation + TTS)
STS_PORT ?= 8003
STS_LOG_FILE := /tmp/claude/sts-service.log
STS_ARTIFACTS_PATH := /tmp/claude/sts-artifacts

sts-full:
	@echo "Starting Full STS Service on port $(STS_PORT)..."
	@mkdir -p /tmp/claude
	@# Kill old instances if running
	@for port in 8000 8001 8002 8003; do \
		pid=$$(lsof -ti:$$port 2>/dev/null || echo ""); \
		if [ -n "$$pid" ]; then \
			echo "  Stopping old instance on port $$port (PID $$pid)..."; \
			kill $$pid 2>/dev/null || true; \
		fi \
	done
	@# Wait for ports to be released
	@echo "  Waiting for ports to be released..."
	@for i in 1 2 3 4 5; do \
		if lsof -ti:$(STS_PORT) >/dev/null 2>&1; then \
			sleep 1; \
		else \
			break; \
		fi \
	done
	@# Final check
	@if lsof -ti:$(STS_PORT) >/dev/null 2>&1; then \
		echo "❌ Port $(STS_PORT) still in use after 5 seconds"; \
		echo "   Try manually: make sts-full-stop"; \
		exit 1; \
	fi
	@echo "  Starting Full STS Service..."
	@PORT=$(STS_PORT) \
		ENABLE_ARTIFACT_LOGGING=true \
		ARTIFACTS_PATH=$(STS_ARTIFACTS_PATH) \
		nohup $(VENV_PYTHON) -m sts_service.full > $(STS_LOG_FILE) 2>&1 & \
		echo $$! > /tmp/claude/sts-service.pid
	@sleep 2
	@if lsof -ti:$(STS_PORT) >/dev/null 2>&1; then \
		echo "✅ Full STS Service started successfully!"; \
		echo "   Port: $(STS_PORT)"; \
		echo "   PID: $$(cat /tmp/claude/sts-service.pid)"; \
		echo "   Logs: $(STS_LOG_FILE)"; \
		echo "   Artifacts: $(STS_ARTIFACTS_PATH)"; \
		echo ""; \
		echo "Monitor logs: make sts-full-logs"; \
		echo "Check status: make sts-full-status"; \
		echo "Stop service: make sts-full-stop"; \
	else \
		echo "❌ Failed to start Full STS Service"; \
		echo "Check logs: tail -50 $(STS_LOG_FILE)"; \
		exit 1; \
	fi

sts-full-stop:
	@echo "Stopping Full STS Service..."
	@if [ -f /tmp/claude/sts-service.pid ]; then \
		pid=$$(cat /tmp/claude/sts-service.pid); \
		if kill $$pid 2>/dev/null; then \
			echo "✅ Service stopped (PID $$pid)"; \
			rm /tmp/claude/sts-service.pid; \
		else \
			echo "⚠️  Process not found (PID $$pid)"; \
			rm /tmp/claude/sts-service.pid; \
		fi \
	else \
		echo "⚠️  No PID file found. Checking ports..."; \
		for port in 8000 8001 8002 8003; do \
			pid=$$(lsof -ti:$$port 2>/dev/null || echo ""); \
			if [ -n "$$pid" ]; then \
				echo "  Killing process on port $$port (PID $$pid)..."; \
				kill $$pid 2>/dev/null || true; \
			fi \
		done; \
		echo "✅ Cleanup complete"; \
	fi

sts-full-logs:
	@echo "📋 Tailing Full STS Service logs ($(STS_LOG_FILE))..."
	@echo "   Press Ctrl+C to exit"
	@echo ""
	@tail -f $(STS_LOG_FILE)

sts-full-status:
	@echo "=== Full STS Service Status ==="
	@if [ -f /tmp/claude/sts-service.pid ]; then \
		pid=$$(cat /tmp/claude/sts-service.pid); \
		if ps -p $$pid > /dev/null 2>&1; then \
			echo "Status: ✅ RUNNING"; \
			echo "PID: $$pid"; \
			port=$$(lsof -nP -p $$pid 2>/dev/null | grep LISTEN | awk '{print $$9}' | cut -d: -f2 | head -1); \
			if [ -n "$$port" ]; then \
				echo "Port: $$port"; \
			fi; \
		else \
			echo "Status: ❌ NOT RUNNING (stale PID file)"; \
			rm /tmp/claude/sts-service.pid; \
		fi \
	else \
		echo "Status: ❌ NOT RUNNING"; \
		echo ""; \
		echo "Checking for orphaned processes..."; \
		for port in 8000 8001 8002 8003; do \
			pid=$$(lsof -ti:$$port 2>/dev/null || echo ""); \
			if [ -n "$$pid" ]; then \
				echo "  Found orphaned process on port $$port (PID $$pid)"; \
			fi \
		done; \
	fi
	@echo ""
	@echo "Logs: $(STS_LOG_FILE)"
	@echo "Artifacts: $(STS_ARTIFACTS_PATH)"

# =============================================================================
# E2E Testing (Cross-Service)
# =============================================================================
# NOTE: E2E tests use DualComposeManager to manage separate Docker Compose
#       environments for media-service and STS-service (spec 021).
#       Services are started automatically by pytest fixtures.
# =============================================================================

# Manual service management (for debugging)
# Uses same .env files as DualComposeManager for consistency
e2e-media-up:
	@echo "Starting media-service E2E environment (MediaMTX + media-service)..."
	@echo "Using environment from tests/e2e/.env.media"
	docker compose -f apps/media-service/docker-compose.yml --env-file tests/e2e/.env.media -p e2e-media up -d --build

e2e-media-down:
	@echo "Stopping media-service E2E environment..."
	docker compose -f apps/media-service/docker-compose.yml -p e2e-media down -v --remove-orphans

e2e-sts-up:
	@echo "Starting STS-service E2E environment (echo-sts for testing)..."
	@echo "Using environment from tests/e2e/.env.sts"
	docker compose -f apps/sts-service/docker-compose.yml --env-file tests/e2e/.env.sts -p e2e-sts up echo-sts -d --build

e2e-sts-down:
	@echo "Stopping STS-service E2E environment..."
	docker compose -f apps/sts-service/docker-compose.yml -p e2e-sts down -v --remove-orphans

e2e-logs:
	@echo "Viewing logs from both E2E environments..."
	@echo "=== Media Service Logs ==="
	@docker compose -f apps/media-service/docker-compose.yml -p e2e-media logs --tail=50 || true
	@echo ""
	@echo "=== STS Service Logs ==="
	@docker compose -f apps/sts-service/docker-compose.yml -p e2e-sts logs --tail=50 || true

# Run E2E tests (DualComposeManager handles service lifecycle)
e2e-test:
	@echo "Running cross-service E2E tests (real media-service + real STS-service)..."
	@echo "Services will be started automatically by pytest fixtures"
	$(VENV_PYTHON) -m pytest tests/e2e/ -v -m e2e --log-cli-level=INFO

# Run only P1 (critical) E2E tests - full pipeline with real services
e2e-test-p1:
	@echo "Running P1 E2E tests (full pipeline with real STS - no mocking)..."
	$(VENV_PYTHON) -m pytest tests/e2e/ -v -m "e2e and full_pipeline" --log-cli-level=INFO

# Clean up all E2E services
e2e-clean:
	@echo "Cleaning up all E2E Docker resources..."
	@docker compose -f apps/media-service/docker-compose.yml -p e2e-media down -v --remove-orphans 2>/dev/null || true
	@docker compose -f apps/sts-service/docker-compose.yml -p e2e-sts down -v --remove-orphans 2>/dev/null || true
	@echo "✓ E2E cleanup complete"

# =============================================================================
# Full STS Service (Docker)
# =============================================================================
# Uses docker-compose.full.yml with real ASR + Translation + TTS
# Requires: .env file with DEEPL_AUTH_KEY and ELEVENLABS_API_KEY
# =============================================================================

sts-docker:
	@echo "Starting Full STS Service in Docker..."
	@echo "Prerequisites: apps/sts-service/.env must contain DEEPL_AUTH_KEY and ELEVENLABS_API_KEY"
	@if [ ! -f apps/sts-service/.env ]; then \
		echo "❌ Error: apps/sts-service/.env not found"; \
		echo "   Create it with:"; \
		echo "   cat > apps/sts-service/.env << EOF"; \
		echo "   DEEPL_AUTH_KEY=your-key-here"; \
		echo "   ELEVENLABS_API_KEY=your-key-here"; \
		echo "   EOF"; \
		exit 1; \
	fi
	@# Ensure dubbing-network exists (created by media-service)
	@docker network inspect dubbing-network >/dev/null 2>&1 || \
		docker network create dubbing-network
	docker compose -f $(STS_SERVICE)/docker-compose.full.yml --env-file $(STS_SERVICE)/.env up -d --build
	@echo ""
	@echo "✅ Full STS Service started!"
	@echo "   URL: http://localhost:8000"
	@echo "   Health: curl http://localhost:8000/health"
	@echo "   Logs: make sts-docker-logs"

sts-docker-stop:
	@echo "Stopping Full STS Docker container..."
	docker compose -f $(STS_SERVICE)/docker-compose.full.yml down --remove-orphans
	@echo "✅ Full STS Service stopped"

sts-docker-logs:
	@echo "📋 Viewing Full STS Docker logs..."
	docker compose -f $(STS_SERVICE)/docker-compose.full.yml logs -f --tail=200

sts-docker-status:
	@echo "=== Full STS Docker Status ==="
	@docker compose -f $(STS_SERVICE)/docker-compose.full.yml ps
	@echo ""
	@echo "Health check:"
	@curl -s http://localhost:8000/health 2>/dev/null && echo "" || echo "❌ Service not responding"

# =============================================================================
# Lightweight STS Service with ElevenLabs (Docker)
# =============================================================================
# Uses docker-compose.elevenlabs.yml - faster build, smaller image (~70% smaller)
# No CUDA, no Coqui TTS - uses ElevenLabs API for TTS
# Requires: .env file with DEEPL_AUTH_KEY and ELEVENLABS_API_KEY
# =============================================================================

sts-elevenlabs:
	@echo "Starting Lightweight STS Service (ElevenLabs) in Docker..."
	@echo "Prerequisites: apps/sts-service/.env must contain DEEPL_AUTH_KEY and ELEVENLABS_API_KEY"
	@if [ ! -f apps/sts-service/.env ]; then \
		echo "❌ Error: apps/sts-service/.env not found"; \
		echo "   Create it with:"; \
		echo "   cat > apps/sts-service/.env << EOF"; \
		echo "   DEEPL_AUTH_KEY=your-key-here"; \
		echo "   ELEVENLABS_API_KEY=your-key-here"; \
		echo "   EOF"; \
		exit 1; \
	fi
	@# Ensure dubbing-network exists (created by media-service)
	@docker network inspect dubbing-network >/dev/null 2>&1 || \
		docker network create dubbing-network
	docker compose -f $(STS_SERVICE)/docker-compose.elevenlabs.yml --env-file $(STS_SERVICE)/.env up -d --build
	@echo ""
	@echo "✅ Lightweight STS Service (ElevenLabs) started!"
	@echo "   URL: http://localhost:8000"
	@echo "   Health: curl http://localhost:8000/health"
	@echo "   Logs: make sts-elevenlabs-logs"

sts-elevenlabs-stop:
	@echo "Stopping ElevenLabs STS Docker container..."
	docker compose -f $(STS_SERVICE)/docker-compose.elevenlabs.yml down --remove-orphans
	@echo "✅ ElevenLabs STS Service stopped"

sts-elevenlabs-logs:
	@echo "📋 Viewing ElevenLabs STS Docker logs..."
	docker compose -f $(STS_SERVICE)/docker-compose.elevenlabs.yml logs -f --tail=200

sts-pipeline-view:
	@./scripts/sts-pipeline-view.sh

# =============================================================================
# Integrated Development (Media + STS Docker)
# =============================================================================
# Starts both media-service and Full STS Service for local development/testing
# Services communicate via shared dubbing-network
# =============================================================================

TEST_FIXTURE := tests/fixtures/test-streams/1-min-nfl.mp4

dev-up:
	@echo "🚀 Starting integrated development environment..."
	@echo ""
	@echo "Step 1: Starting media-service (creates dubbing-network)..."
	docker compose -f $(MEDIA_SERVICE)/docker-compose.yml up -d --build
	@echo ""
	@echo "Step 2: Starting Full STS Service (joins dubbing-network)..."
	@if [ ! -f apps/sts-service/.env ]; then \
		echo "⚠️  Warning: apps/sts-service/.env not found"; \
		echo "   STS will fail without API keys. Create .env first."; \
		exit 1; \
	fi
	docker compose -f $(STS_SERVICE)/docker-compose.full.yml --env-file $(STS_SERVICE)/.env up -d --build
	@echo ""
	@echo "✅ All services started!"
	@echo ""
	@echo "Services:"
	@echo "  MediaMTX:       rtmp://localhost:1935 (RTMP), rtsp://localhost:8554 (RTSP)"
	@echo "  MediaMTX API:   http://localhost:9997/v3/paths/list"
	@echo "  Media Service:  http://localhost:8080/health"
	@echo "  STS Service:    http://localhost:8000/health"
	@echo ""
	@echo "Commands:"
	@echo "  make dev-logs   - View logs from all services"
	@echo "  make dev-test   - Publish test fixture"
	@echo "  make dev-down   - Stop all services"

dev-up-light:
	@echo "🚀 Starting lightweight development environment (ElevenLabs TTS)..."
	@echo ""
	@echo "Step 1: Starting media-service (creates dubbing-network)..."
	docker compose -f $(MEDIA_SERVICE)/docker-compose.yml up -d --build
	@echo ""
	@echo "Step 2: Starting Lightweight STS Service (ElevenLabs)..."
	@if [ ! -f apps/sts-service/.env ]; then \
		echo "⚠️  Warning: apps/sts-service/.env not found"; \
		echo "   STS will fail without API keys. Create .env first."; \
		exit 1; \
	fi
	docker compose -f $(STS_SERVICE)/docker-compose.elevenlabs.yml --env-file $(STS_SERVICE)/.env up -d --build
	@echo ""
	@echo "✅ All services started (lightweight mode)!"
	@echo ""
	@echo "Services:"
	@echo "  MediaMTX:       rtmp://localhost:1935 (RTMP), rtsp://localhost:8554 (RTSP)"
	@echo "  MediaMTX API:   http://localhost:9997/v3/paths/list"
	@echo "  Media Service:  http://localhost:8080/health"
	@echo "  STS Service:    http://localhost:8000/health (ElevenLabs TTS)"
	@echo ""
	@echo "Commands:"
	@echo "  make dev-logs   - View logs from all services"
	@echo "  make dev-test   - Publish test fixture"
	@echo "  make dev-down   - Stop all services"

dev-down:
	@echo "🛑 Stopping all development services..."
	@docker compose -f $(STS_SERVICE)/docker-compose.full.yml down --remove-orphans 2>/dev/null || true
	@docker compose -f $(STS_SERVICE)/docker-compose.elevenlabs.yml down --remove-orphans 2>/dev/null || true
	@docker compose -f $(MEDIA_SERVICE)/docker-compose.yml down -v --remove-orphans 2>/dev/null || true
	@echo "✅ All services stopped"

dev-logs:
	@echo "📋 Viewing logs from all services..."
	@echo "Press Ctrl+C to exit"
	@echo ""
	@echo "=== Media Service + MediaMTX Logs ==="
	@docker compose -f $(MEDIA_SERVICE)/docker-compose.yml logs -f --tail=100 &
	@echo ""
	@echo "=== Full STS Service Logs ==="
	@docker compose -f $(STS_SERVICE)/docker-compose.full.yml logs -f --tail=100

dev-ps:
	@echo "=== Running Development Containers ==="
	@echo ""
	@echo "Media Service Stack:"
	@docker compose -f $(MEDIA_SERVICE)/docker-compose.yml ps
	@echo ""
	@echo "STS Service Stack:"
	@docker compose -f $(STS_SERVICE)/docker-compose.full.yml ps

dev-test:
	@echo "🎬 Publishing test fixture to media-service..."
	@if [ ! -f $(TEST_FIXTURE) ]; then \
		echo "❌ Test fixture not found: $(TEST_FIXTURE)"; \
		exit 1; \
	fi
	@echo ""
	@echo "Checking services..."
	@curl -sf http://localhost:8080/health >/dev/null || (echo "❌ Media service not running. Run 'make dev-up' first." && exit 1)
	@curl -sf http://localhost:8000/health >/dev/null || (echo "❌ STS service not running. Run 'make dev-up' first." && exit 1)
	@echo "✅ All services healthy"
	@echo ""
	@echo "Publishing $(TEST_FIXTURE) to rtmp://localhost:1935/live/test_stream/in"
	@echo "Output will be at: rtmp://localhost:1935/live/test_stream/out"
	@echo ""
	@echo "Press Ctrl+C to stop publishing"
	@echo ""
	ffmpeg -re -stream_loop -1 \
		-i $(TEST_FIXTURE) \
		-c copy \
		-f flv rtmp://localhost:1935/live/test_stream/in

# Stream name for dev-push/dev-play commands
DEV_STREAM_NAME ?= test-stream
DEV_SPEECH_FIXTURE := tests/fixtures/test-streams/speech_zh.mp4

dev-push:
	@echo "🎬 Pushing test stream to media-service..."
	@if [ ! -f $(DEV_SPEECH_FIXTURE) ]; then \
		echo "❌ Test fixture not found: $(DEV_SPEECH_FIXTURE)"; \
		exit 1; \
	fi
	@echo ""
	@echo "Checking services..."
	@curl -sf http://localhost:8080/health >/dev/null || (echo "❌ Media service not running. Run 'make dev-up-light' first." && exit 1)
	@curl -sf http://localhost:8000/health >/dev/null || (echo "❌ STS service not running. Run 'make dev-up-light' first." && exit 1)
	@echo "✅ All services healthy"
	@echo ""
	@echo "Publishing $(DEV_SPEECH_FIXTURE) to rtmp://localhost:1935/live/$(DEV_STREAM_NAME)/in"
	@echo "Output will be at: rtmp://localhost:1935/live/$(DEV_STREAM_NAME)/out"
	@echo ""
	@echo "To play output: make dev-play"
	@echo "To play input:  make dev-play-in"
	@echo ""
	@echo "Press Ctrl+C to stop"
	@echo ""
	ffmpeg -re -stream_loop -1 \
		-i $(DEV_SPEECH_FIXTURE) \
		-c:v libx264 -preset veryfast -tune zerolatency \
		-c:a aac -b:a 128k \
		-f flv "rtmp://localhost:1935/live/$(DEV_STREAM_NAME)/in"

dev-play:
	@echo "🎧 Playing dubbed output stream..."
	@echo "Stream: rtsp://localhost:8554/live/$(DEV_STREAM_NAME)/out"
	@echo ""
	@echo "Checking if stream is active..."
	@curl -sf http://localhost:9997/v3/paths/list | grep -q "$(DEV_STREAM_NAME)/out" || \
		(echo "⚠️  Output stream not found. Make sure 'make dev-push' is running and pipeline has processed some data." && exit 1)
	@echo "✅ Stream found, starting playback..."
	@echo ""
	@echo "Press Q or Ctrl+C to stop"
	@echo ""
	ffplay -fflags nobuffer -flags low_delay -framedrop \
		"rtsp://localhost:8554/live/$(DEV_STREAM_NAME)/out"

dev-play-in:
	@echo "🎧 Playing input stream (for comparison)..."
	@echo "Stream: rtsp://localhost:8554/live/$(DEV_STREAM_NAME)/in"
	@echo ""
	@echo "Checking if stream is active..."
	@curl -sf http://localhost:9997/v3/paths/list | grep -q "$(DEV_STREAM_NAME)/in" || \
		(echo "⚠️  Input stream not found. Make sure 'make dev-push' is running." && exit 1)
	@echo "✅ Stream found, starting playback..."
	@echo ""
	@echo "Press Q or Ctrl+C to stop"
	@echo ""
	ffplay -fflags nobuffer -flags low_delay -framedrop \
		"rtsp://localhost:8554/live/$(DEV_STREAM_NAME)/in"
