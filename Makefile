.PHONY: dev down logs ps

dev:
	docker compose -f deploy/docker-compose.yml up --build

down:
	docker compose -f deploy/docker-compose.yml down --remove-orphans

logs:
	docker compose -f deploy/docker-compose.yml logs -f --tail=200

ps:
	docker compose -f deploy/docker-compose.yml ps

