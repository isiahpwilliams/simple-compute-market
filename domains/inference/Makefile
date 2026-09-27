DIST_DIR ?= ../../.dist

.PHONY: reinit test

# The domain's own tests import this package from its installed wheel; see `cache-keys` in pyproject.toml.
reinit test: export UV_NO_EDITABLE := 1

reinit: ## Force-reinstall internal wheels without bumping versions. Run make dist from the monorepo root first.
	uv sync --dev --find-links $(DIST_DIR) \
		--upgrade-package arkhai-inference-domain --reinstall-package arkhai-inference-domain \
		--upgrade-package arkhai-core --reinstall-package arkhai-core \
		--upgrade-package arkhai-kit-policy --reinstall-package arkhai-kit-policy \
		--upgrade-package arkhai-kit-identity --reinstall-package arkhai-kit-identity

test: reinit ## Domain-package-level tests (models, pricing, codecs, usage, distribution)
	uv run --find-links $(DIST_DIR) pytest tests -q
