.PHONY: db-up db-down seed seed-ca deploy-api deploy-web deploy

db-up:
	docker compose -f infra/docker-compose.yml up -d

db-down:
	docker compose -f infra/docker-compose.yml down

seed:
	cd apps/api && uv run python -m campscout.seed.recreation_gov

seed-ca:
	cd apps/api && uv run python -m campscout.seed.reserve_california

deploy-api:
	cd apps/api && fly deploy

deploy-web:
	cd apps/web && vercel --prod

deploy: deploy-api deploy-web
