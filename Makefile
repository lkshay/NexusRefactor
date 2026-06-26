# Common commands. Run `make help` for the list.
.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

sync: ## Install/update all deps into .venv (incl. dev group)
	uv sync

up: ## Start local Qdrant (docker)
	docker compose up -d qdrant

down: ## Stop local Qdrant
	docker compose down

test: ## Run the test suite
	uv run pytest

typecheck: ## mypy over our source (NOT the verify gate — that runs in the sandbox)
	uv run mypy src

lint: ## Lint with ruff
	uv run ruff check .

fmt: ## Auto-format with ruff
	uv run ruff format .

eval: ## Run the evaluation harness over the golden set
	uv run python -m eval.run_eval

run: ## Run the agent on one scenario, e.g. `make run SCENARIO=eval/golden/example_rename_field`
	uv run nexus run $(SCENARIO)

.PHONY: help sync up down test typecheck lint fmt eval run
