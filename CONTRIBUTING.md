# Contributing to ICV Open Source

Practical guide for contributors working on the icv-oss monorepo.

---

## Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Django 5.1 or later (installed as part of the dev setup)
- PostgreSQL 14+ (required by `icv-search` and `django-boundary` tests only)

---

## Local Development Setup

```bash
git clone https://github.com/icv-oss/icv-oss.git
cd icv-oss

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install all packages in editable mode plus test dependencies
make install-dev
```

Or manually with pip:

```bash
pip install -e packages/icv-core
pip install -e packages/icv-tree
pip install -e packages/icv-search
pip install -e packages/icv-sitemaps
pip install -e packages/icv-taxonomy
pip install -e packages/django-boundary
pip install "Django~=5.1" pytest pytest-django pytest-cov pytest-mock factory-boy djangorestframework django-filter
```

---

## Running Tests

Each package has its own `tests/` directory and `tests/settings.py`. Tests are run with pytest, with `DJANGO_SETTINGS_MODULE` and `PYTHONPATH` set per package.

### Run all packages

```bash
make test
```

### Run a single package

```bash
make test-pkg PKG=icv-tree
```

### Run manually

```bash
# icv-core (SQLite)
DJANGO_SETTINGS_MODULE=settings \
PYTHONPATH=packages/icv-core/src:packages/icv-core/tests \
pytest packages/icv-core/tests/ -v --tb=short

# icv-tree (SQLite)
DJANGO_SETTINGS_MODULE=settings \
PYTHONPATH=packages/icv-tree/src:packages/icv-tree/tests \
pytest packages/icv-tree/tests/ -v --tb=short

# icv-search (PostgreSQL — requires DB_* env vars)
DJANGO_SETTINGS_MODULE=settings \
PYTHONPATH=packages/icv-search/src:packages/icv-search/tests \
DB_NAME=icv_test_db DB_USER=icv_test DB_PASSWORD=icv_test_password \
DB_HOST=localhost DB_PORT=5432 \
pytest packages/icv-search/tests/ -v --tb=short

# icv-sitemaps (SQLite)
DJANGO_SETTINGS_MODULE=settings \
PYTHONPATH=packages/icv-sitemaps/src:packages/icv-sitemaps/tests \
pytest packages/icv-sitemaps/tests/ -v --tb=short

# icv-taxonomy (SQLite — depends on icv-tree)
DJANGO_SETTINGS_MODULE=settings \
PYTHONPATH=packages/icv-taxonomy/src:packages/icv-taxonomy/tests:packages/icv-tree/src \
pytest packages/icv-taxonomy/tests/ -v --tb=short

# django-boundary (PostgreSQL — requires POSTGRES_* env vars)
DJANGO_SETTINGS_MODULE=settings \
PYTHONPATH=packages/django-boundary/src:packages/django-boundary/tests \
POSTGRES_USER=icv_test POSTGRES_PASSWORD=icv_test_password \
POSTGRES_DB=icv_test_db POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
pytest packages/django-boundary/tests/ -v --tb=short
```

---

## Code Standards

All Python code is linted and formatted with [ruff](https://docs.astral.sh/ruff/), configured in the root `pyproject.toml`.

| Setting | Value |
|---------|-------|
| Line length | 120 |
| Quote style | Double |
| Target Python | 3.11 |

```bash
make lint      # ruff check
make format    # ruff format (writes in place)
make check     # both, no writes (what CI runs)
```

CI will fail if either check reports errors. Run `make check` before pushing.

---

## Package Structure

Each package is independent with its own `pyproject.toml` and follows the src layout:

```
packages/<package-name>/
    src/<module_name>/      # importable package (e.g. icv_tree, boundary)
    tests/
        settings.py         # Django settings for the test suite
    pyproject.toml          # package metadata, dependencies, pytest config
    CHANGELOG.md
    README.md
```

Packages are published independently to PyPI. The root `pyproject.toml` contains shared tooling configuration only — it is not itself a package.

### Dependency rule

Every package may depend on `django-icv-core`. There are no other inter-package dependencies, with the exception of `icv-taxonomy` which also depends on `icv-tree`. `django-boundary` is fully standalone.

---

## Git Workflow

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `chore` | Maintenance, version bumps, dependency updates |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `style` | Formatting, whitespace — no logic change |
| `refactor` | Code change that is neither a fix nor a feature |

Scope is the package name without the `django-` or `icv-` prefix, e.g. `feat(tree): add async-safe rebuild`.

### Branches and PRs

Push feature branches to a fork and open a pull request against `main`. CI must pass before merging. Prefer small, focused commits over large ones.

---

## Releasing

Releases are triggered by pushing a tag. PyPI publishing is handled by CI automatically when a matching tag lands on `main`.

### Steps

1. **Bump the version** in `packages/<name>/pyproject.toml` and `packages/<name>/src/<module>/__init__.py`:

   ```python
   __version__ = "0.2.0"
   ```

2. **Update `CHANGELOG.md`** for the package — move items from `[Unreleased]` to a new versioned section:

   ```markdown
   ## [0.2.0] — 2026-04-07

   ### Added
   - ...

   ### Fixed
   - ...
   ```

3. **Commit**:

   ```bash
   git add packages/<name>/
   git commit -m "chore(<scope>): bump <package> to v<version>"
   ```

4. **Tag** using the monorepo tag format:

   ```bash
   git tag <package-name>/v<version>
   # e.g. git tag icv-tree/v0.2.0
   ```

5. **Push** the commit and tag:

   ```bash
   git push origin main
   git push origin <package-name>/v<version>
   ```

The tag push triggers the PyPI publish workflow in CI.
