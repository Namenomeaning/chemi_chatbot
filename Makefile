.PHONY: check test dev deploy smoke knowledge
check:
	cd backend && uv run ruff check src tests scripts
	cd backend && uv run ruff format --check src tests scripts
	$(MAKE) test

test:
	cd backend && uv run pytest -q
	cd backend && uv run python scripts/evaluate_retrieval.py

dev:
	cd backend && uv run pywrangler dev

deploy: check
	cd backend && uv run pywrangler deploy
	$(MAKE) smoke

smoke:
	bash backend/smoke.sh https://chemi.quangiz.me

knowledge:
	cd backend && uv run python scripts/build_knowledge.py
