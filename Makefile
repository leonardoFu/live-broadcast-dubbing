.PHONY: dev down logs ps fmt lint typecheck test

PYTHON ?= python3

dev:
	docker compose -f deploy/docker-compose.yml up --build

down:
	docker compose -f deploy/docker-compose.yml down --remove-orphans

logs:
	docker compose -f deploy/docker-compose.yml logs -f --tail=200

ps:
	docker compose -f deploy/docker-compose.yml ps

fmt:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .

typecheck:
	@PY_FILES=$$(find . -type f \( -name '*.py' -o -name '*.pyi' \) \
		-not -path './.venv/*' \
		-not -path './.codex/*' \
		-not -path './.project-scripts/*' \
		-not -path './.specify/*' \
		-not -path './.sts-service-archive/*' \
		-not -path './specs/*'); \
	if [ -z "$$PY_FILES" ]; then echo "No Python files to typecheck."; exit 0; fi; \
	$(PYTHON) -m mypy $$PY_FILES

test:
	$(PYTHON) -m pytest -q
