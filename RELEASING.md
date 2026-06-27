# Releasing

How to cut a release for any package in this monorepo. Packages are versioned
and published **independently** to PyPI. Each has its own
`packages/<pkg>/CHANGELOG.md`, its own version, and its own
`.github/workflows/publish-<pkg>.yml`.

## TL;DR

```
branch  →  PR  →  review  →  merge to main  →  tag the merged commit  →  CI publishes
```

The **tag is the trigger**. Pushing a tag of the form `<pypi-name>/v<semver>`
runs the publish workflow, which tests, builds, uploads to PyPI (OIDC trusted
publishing — no token), and creates a GitHub release. **Tagging is publishing.
There is no separate "publish" step and no undo.**

## Canonical flow

1. **Branch** off `main`:
   `release/<pkg>-<version>` (e.g. `release/django-boundary-0.4.0`).
2. **Bump** on the branch:
   - `packages/<pkg>/pyproject.toml` → `version`
   - `packages/<pkg>/src/<module>/__init__.py` → `__version__` (keep in sync)
   - `packages/<pkg>/CHANGELOG.md` → rename `[Unreleased]` to
     `[<version>] — <YYYY-MM-DD>` (today's date)
3. **Open a PR** to `main`. CI runs lint + tests. Get it reviewed. This is the
   gate — do not skip it.
4. **Merge to `main`** (squash or merge, per repo norm).
5. **Tag the merged commit on `main`** and push the tag:
   ```bash
   git checkout main && git pull
   git tag <pypi-name>/v<version>      # lightweight tag
   git push origin <pypi-name>/v<version>
   ```
6. **Watch the publish run** and confirm PyPI:
   ```bash
   gh run watch <run-id> --exit-status
   curl -s https://pypi.org/pypi/<pypi-name>/json | python -c \
     "import sys,json;print(json.load(sys.stdin)['info']['version'])"
   ```

> **Tag the commit that is on `main`, not a feature branch.** Tags point at
> commits, not branches, so tagging a feature branch *will* publish — but it
> publishes code that may never have been merged. Always tag after the merge so
> what's on PyPI is exactly what's on `main`.

## Tag format (strict)

`<pypi-name>/v<semver>` — the PyPI distribution name, then `/v`, then the
version. The publish workflow matches `<pypi-name>/v*` and parses the version
from after `/v`.

| Package (PyPI name) | Tag example |
| --- | --- |
| `django-boundary` | `django-boundary/v0.4.0` |
| `icv-core` | `icv-core/v0.3.0` |
| `icv-tree` | `icv-tree/v0.2.1` |
| `icv-search` | `icv-search/v1.1.3` |
| `icv-sitemaps` | `icv-sitemaps/v0.6.0` |
| `icv-taxonomy` | `icv-taxonomy/v0.4.0` |

**Use the full PyPI name.** A historical `boundary/v0.2.0` tag exists and does
**not** match the `django-boundary/v*` trigger — it never published. Don't
reintroduce short prefixes.

## Versioning (SemVer)

[Semantic Versioning](https://semver.org/). Pre-1.0, the rules still apply with
the usual pre-1.0 caveat that minor bumps may carry breaking changes:

- **Patch** (`0.3.1 → 0.3.2`): bug fixes, doc-only changes, no API or behaviour
  change.
- **Minor** (`0.3.1 → 0.4.0`): new public API, **any behaviour change** (even a
  safer one), or a raised minimum dependency floor (e.g. Django).
- **Major** (`0.x → 1.0`): the stability commitment; breaking changes after 1.0.

If in doubt between patch and minor, choose minor. Burning a version number is
free; shipping a behaviour change as a patch surprises consumers.

## CHANGELOG (required — every release)

**A release MUST include a CHANGELOG entry for its version. No entry, no tag.**
Every published version needs a dated section in `packages/<pkg>/CHANGELOG.md`;
a release with no changelog entry is incomplete and should not be tagged.

[Keep a Changelog](https://keepachangelog.com/) format. Accumulate entries under
`## [Unreleased]` as you work; at release time, rename that heading to
`## [<version>] — <YYYY-MM-DD>`. Subsections: Added / Changed / Fixed / Removed.
Call out behaviour changes explicitly, including ones that are "safer" — a
consumer relying on the old behaviour still needs to know.

The GitHub release body is generated from the tag (auto-generated notes), but
that is **not** a substitute for the curated CHANGELOG entry — write the
CHANGELOG by hand so consumers reading the package on PyPI/GitHub get a
human-authored summary, not just a commit list.

## Where planning docs go

Triage notes, design plans, and other internal working documents go in
`docs/plans/` at the repo root, which is **gitignored** (kept on disk as a
historical record, not committed). User-facing package documentation belongs in
the package's own `packages/<pkg>/docs/` tree and **is** committed. See
`docs/plans/README.md` for the distinction.

## Keep the CI Django pin in step with the floor

Each `publish-<pkg>.yml` test job pins a Django version for the pre-publish test
run. When you raise a package's minimum Django in `pyproject.toml`, **update the
pin in the same PR**, or the tagged build's test job can fail to resolve
dependencies and block the publish. (This bit us once: floor moved to 5.2 while
the workflow still pinned `Django~=5.1.0`.)

## Pre-tag checklist

Before pushing the tag (the irreversible step):

- [ ] **CHANGELOG has a `[<version>] — <date>` entry** (renamed from
      `[Unreleased]`). This is mandatory — every release ships with a changelog.
- [ ] Behaviour changes and breaking changes called out in that CHANGELOG entry.
- [ ] Version bumped in `pyproject.toml` **and** `__init__.py`, and they match.
- [ ] CI Django pin matches the package's minimum, if the floor changed.
- [ ] Tests pass locally and the package builds (`python -m build` in the
      package dir).
- [ ] The PR is **merged to `main`** and you are tagging that commit.
- [ ] Tag format is `<full-pypi-name>/v<version>`.
- [ ] This exact version has never been published (PyPI rejects re-uploads).

## If something goes wrong

- **PyPI rejects the upload (version exists).** That version is permanently
  taken — you cannot re-upload, even after deleting. Bump to the next patch and
  re-tag.
- **The test/build job fails after tagging.** Nothing was published (publish is
  the last job and depends on test+build). Fix on a new PR, merge, delete the
  bad tag (`git push --delete origin <tag>`), and re-tag the new commit with the
  **same** version (since nothing reached PyPI).
- **Published, but the code isn't on `main`.** Open a PR from the release branch
  to `main` immediately and merge, so `main` reflects what's on PyPI. Avoid this
  by always tagging after the merge.

## Optional hardening

Consider adding a **manual approval gate** to the `publish` job via a protected
GitHub Environment (`pypi`), so "push tag" and "irreversibly upload to PyPI" are
decoupled — a human approves the upload after seeing test+build go green. The
workflows already declare `environment: pypi`; add a required-reviewer
protection rule to that environment to enable the gate.
