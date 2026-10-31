# Every uv command in this Makefile uses the repository's declared Python version.
export UV_PYTHON := $(or $(shell cat ../../../.python-version 2>/dev/null),$(error ../../../.python-version not found))

DIST_DIR ?= ../../../.dist

.PHONY: init reinit test

init: reinit

# Refresh the internal wheels the lock installs; run `make dist` at the repository root first.
reinit:
	python3 ../../../scripts/uv_project.py reinit

test: reinit
	uv run --find-links $(DIST_DIR) pytest tests -q
