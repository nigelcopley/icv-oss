PACKAGES = icv-core icv-tree icv-search icv-sitemaps icv-taxonomy django-boundary

.PHONY: lint format check test test-pkg build install-dev clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

lint: ## Run ruff linter
	ruff check .

format: ## Run ruff formatter
	ruff format .

check: ## Run both lint and format check (no writes — mirrors CI)
	ruff check .
	ruff format --check .

install-dev: ## Install all packages in editable mode with test dependencies
	pip install -e packages/icv-core
	pip install -e packages/icv-tree
	pip install -e packages/icv-search
	pip install -e packages/icv-sitemaps
	pip install -e packages/icv-taxonomy
	pip install -e packages/django-boundary
	pip install "Django~=5.1" pytest pytest-django pytest-cov pytest-mock factory-boy djangorestframework django-filter psycopg2-binary "psycopg[binary]"

test: ## Run all package tests sequentially
	@$(MAKE) _test-icv-core
	@$(MAKE) _test-icv-tree
	@$(MAKE) _test-icv-search
	@$(MAKE) _test-icv-sitemaps
	@$(MAKE) _test-icv-taxonomy
	@$(MAKE) _test-django-boundary

# Single-package test: make test-pkg PKG=icv-search
test-pkg: ## Run tests for a single package: make test-pkg PKG=icv-search
ifndef PKG
	$(error PKG is not set. Usage: make test-pkg PKG=icv-search)
endif
	@$(MAKE) _test-$(PKG)

build: ## Build all packages (wheel + sdist)
	@for pkg in $(PACKAGES); do \
		echo "Building $$pkg..."; \
		cd packages/$$pkg && python -m build && cd ../..; \
	done

clean: ## Remove build artifacts
	@find packages -type d -name dist -exec rm -rf {} + 2>/dev/null; \
	find packages -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type f -name "*.pyc" -delete 2>/dev/null; \
	echo "Clean."

# ---------------------------------------------------------------------------
# Internal per-package test targets
# ---------------------------------------------------------------------------

_test-icv-core:
	DJANGO_SETTINGS_MODULE=settings \
	PYTHONPATH=packages/icv-core/src:packages/icv-core/tests \
	pytest packages/icv-core/tests/ -v --tb=short --color=yes

_test-icv-tree:
	DJANGO_SETTINGS_MODULE=settings \
	PYTHONPATH=packages/icv-tree/src:packages/icv-tree/tests \
	pytest packages/icv-tree/tests/ -v --tb=short --color=yes

_test-icv-search:
	DJANGO_SETTINGS_MODULE=settings \
	PYTHONPATH=packages/icv-search/src:packages/icv-search/tests \
	pytest packages/icv-search/tests/ -v --tb=short --color=yes

_test-icv-sitemaps:
	DJANGO_SETTINGS_MODULE=settings \
	PYTHONPATH=packages/icv-sitemaps/src:packages/icv-sitemaps/tests \
	pytest packages/icv-sitemaps/tests/ -v --tb=short --color=yes

_test-icv-taxonomy:
	DJANGO_SETTINGS_MODULE=settings \
	PYTHONPATH=packages/icv-taxonomy/src:packages/icv-taxonomy/tests:packages/icv-tree/src \
	pytest packages/icv-taxonomy/tests/ -v --tb=short --color=yes

_test-django-boundary:
	DJANGO_SETTINGS_MODULE=settings \
	PYTHONPATH=packages/django-boundary/src:packages/django-boundary/tests \
	pytest packages/django-boundary/tests/ -v --tb=short --color=yes
