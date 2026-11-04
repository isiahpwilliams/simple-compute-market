# Every uv command in this Makefile uses the repository's declared Python version.
export UV_PYTHON := $(or $(shell cat ../../.python-version 2>/dev/null),$(error ../../.python-version not found))

DIST_DIR ?= ../../.dist

.PHONY: reinit test test-domain test-service test-storefront test-buyer test-sample-app

test: test-domain test-service test-storefront test-buyer test-sample-app

reinit: ## Force-reinstall internal wheels without bumping versions. Run make dist from the monorepo root first.
	python3 ../../scripts/uv_project.py reinit

test-domain: reinit ## Domain-package-level tests (distribution/wheel-import + credits client contract)
	uv run --find-links $(DIST_DIR) pytest tests -q

test-service:
	cd service && make test

test-storefront:
	cd storefront && make test

test-buyer:
	cd buyer && make test

test-sample-app:
	cd sample-app && make test
