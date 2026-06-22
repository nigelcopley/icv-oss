#!/usr/bin/env python3
"""Exit 0 if the given package's requires-python admits the running interpreter.

Usage: py_compatible.py <path-to-package-dir>

Used by CI to skip installing/testing packages whose requires-python excludes
the current Python version (for example, django-boundary requires >=3.12 and
must not be installed on the 3.11 matrix leg).
"""

import sys
import tomllib

from packaging.specifiers import SpecifierSet

pkg_dir = sys.argv[1]
with open(f"{pkg_dir}/pyproject.toml", "rb") as fh:
    spec = tomllib.load(fh)["project"].get("requires-python", "")

current = f"{sys.version_info.major}.{sys.version_info.minor}"
sys.exit(0 if (not spec or SpecifierSet(spec).contains(current)) else 1)
