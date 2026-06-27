# Planning archive (gitignored)

This directory holds **working planning documents** — triage notes, design
plans, scratch analysis, migration write-ups — that we want to keep on disk as a
historical record but **not** publish in the repository.

## What goes here

- Implementation plans and triage docs produced while scoping work.
- Field reports, audits, or analysis that informed a change but isn't part of
  the shipped package docs.
- Anything internal/project-specific (e.g. references to private downstream
  codebases) that shouldn't live in a published package's `docs/` tree.

## What does NOT go here

- User-facing package documentation. That belongs in the package's own
  `packages/<pkg>/docs/` tree and IS committed.
- Anything that should be reviewed or versioned with the code.

## How it's wired

The contents of this directory are **gitignored**. Only this `README.md` and a
`.gitkeep` are tracked, so the directory and its purpose exist for everyone who
clones the repo, while the plan files themselves stay local.

See the root `.gitignore` for the exact rule. If you add a file here and want it
in the repo after all, move it into the relevant package's `docs/` tree.
