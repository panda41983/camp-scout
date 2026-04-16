.PHONY: db-up db-down seed seed-ca

db-up:
	docker compose -f infra/docker-compose.yml up -d

db-down:
	docker compose -f infra/docker-compose.yml down

seed:
	cd apps/api && uv run python -m campscout.seed.recreation_gov

seed-ca:
	cd apps/api && uv run python -m campscout.seed.reserve_california
