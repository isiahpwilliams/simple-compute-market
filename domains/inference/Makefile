# Every uv command in this Makefile uses the repository's declared Python version.
export UV_PYTHON := $(or $(shell cat ../../.python-version 2>/dev/null),$(error ../../.python-version not found))

DIST_DIR ?= ../../.dist

.PHONY: reinit test test-domain test-service test-storefront test-buyer

test: test-domain test-service test-storefront test-buyer

reinit: ## Sync this environment, refreshing the internal wheels its lock installs. Run make dist first.
	python3 ../../scripts/uv_project.py reinit

test-domain: reinit ## Domain-package-level tests (models, pricing, codecs, usage, distribution)
	uv run --find-links $(DIST_DIR) pytest tests -q

test-service:
	cd service && make test

test-storefront:
	cd storefront && make test

test-buyer:
	cd buyer && make test
