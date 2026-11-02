# Every uv command in this Makefile uses the repository's declared Python version.
export UV_PYTHON := $(or $(shell cat ../../.python-version 2>/dev/null),$(error ../../.python-version not found))

.PHONY: help reinit test serve

.DEFAULT_GOAL := help

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

reinit: ## Sync this environment.
	python3 ../../scripts/uv_project.py reinit

test: reinit ## Run the stub's unit tests
	uv run pytest tests -q

serve: ## Run the stub locally on port 8000
	uv run uvicorn inference_model_stub.app:app --port 8000
