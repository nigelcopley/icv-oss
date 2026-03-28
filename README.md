# ICV Open Source

Reusable Django packages providing foundational capabilities for modern Django applications.

## Packages

| Package | PyPI | Description |
|---------|------|-------------|
| [django-icv-core](packages/icv-core/) | [![PyPI](https://img.shields.io/pypi/v/django-icv-core)](https://pypi.org/project/django-icv-core/) | Abstract base models, managers, middleware, utilities, and audit logging |
| [django-icv-tree](packages/icv-tree/) | [![PyPI](https://img.shields.io/pypi/v/django-icv-tree)](https://pypi.org/project/django-icv-tree/) | Materialised path tree structures — configurable format, async-safe, no tenancy coupling |
| [django-icv-search](packages/icv-search/) | [![PyPI](https://img.shields.io/pypi/v/django-icv-search)](https://pypi.org/project/django-icv-search/) | Pluggable search engine integration — index management, document indexing, swappable backends |
| [django-icv-sitemaps](packages/icv-sitemaps/) | [![PyPI](https://img.shields.io/pypi/v/django-icv-sitemaps)](https://pypi.org/project/django-icv-sitemaps/) | Scalable sitemap generation, robots.txt, llms.txt, ads.txt, security.txt |
| [django-boundary](packages/django-boundary/) | [![PyPI](https://img.shields.io/pypi/v/django-boundary)](https://pypi.org/project/django-boundary/) | Row-level multi-tenancy for Django with PostgreSQL RLS |

## Requirements

- Python 3.10+
- Django 5.1+

## Installation

Each package is independently installable from PyPI:

```bash
pip install django-icv-core
pip install django-icv-tree
pip install django-icv-search
pip install django-icv-sitemaps
pip install django-boundary
```

## Dependency Rule

Every package depends only on `django-icv-core`. There are no inter-package dependencies. `django-boundary` is fully standalone with no ICV dependencies.

```
django-icv-core    (foundation — no package dependencies)
    ├── django-icv-tree
    ├── django-icv-search
    └── django-icv-sitemaps

django-boundary    (standalone — no ICV dependencies)
```

## Contributing

Issues and pull requests are welcome. Please ensure tests pass and code is formatted with ruff before submitting.

## Licence

MIT
