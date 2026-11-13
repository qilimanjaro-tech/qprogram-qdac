# qprogram-qdac

QProgram QDAC adds the `qdac` vendor namespace (QDevil QDAC operations, their capability profile and their `.qp` form) to the QProgram pulse-level DSL, for platform authors who drive a QDAC for flux biasing. It is public on PyPI under Apache-2.0.

## Navigate by task
- Operations (AST nodes): `src/qprogram_qdac/operations.py`. The `program.qdac.*` builder: `src/qprogram_qdac/namespace.py`, typed through `src/qprogram_qdac/mixin.py`.
- Capability tokens, predicates and the `qdac-default-v1` profile: `src/qprogram_qdac/profiles.py`.
- Registration, the vendor protocol version and the pre-combined `QProgram`: `src/qprogram_qdac/__init__.py`.
- Where a change lands, the new-operation checklist and the release steps: `docs/developer/contributing.md`. What a platform does with each operation: `docs/developer/lowering.md`.
- Tests: `tests/`, one file per module; `.qp` fixture headers come from `tests/_header.py`.
- The AST, the validator and the `.qp` format live in the core `qprogram` package (PyPI; docs at https://qilimanjaro-tech.github.io/qprogram/).
- Before writing or reviewing code or tests: read `CODING_STANDARDS.md` and `REVIEW.md`.
- Domain vocabulary: `GLOSSARY.md`; name code, tests and PRs with its terms. Decisions: `docs/adr/`. Tracker and triage: `docs/agents/`.
- Project knowledge base: TODO(human): link the domain wiki.

## Commands
- Setup: `uv sync --group dev --group docs`. Every dependency, `qprogram` included, resolves from PyPI.
- Focused test: `uv run pytest tests/test_profile.py`
- **Verify (run before calling work done):** `uv run ruff check . && uv run ruff format --diff . && uv run ty check --python-version 3.11 && uv run ty check --python-version 3.12 && uv run ty check --python-version 3.13 && uv run ty check --python-version 3.14 && uv run pytest --cov=qprogram_qdac --cov-report=term-missing && uv run --group docs zensical build --strict`
  (the gates of the Code Quality, Tests and Documentation workflows).

<important if="you edit `docs/`, the README or a public docstring">
- Docs (`docs/`, nav in `zensical.toml`), the README or a public docstring: follow `.claude/skills/qprogram-docs/SKILL.md`.
- Docs checker: `uv run python .claude/skills/qprogram-docs/scripts/check_docs.py docs`
</important>

## Boundaries
- Validate with synthetic inputs and offline tests; hardware, lab databases and production runcards are in scope only when the task names them.
- Report every gate you could not run and why.
- Keep credentials, runcards with real addresses and measurement data out of the repository and out of agent instructions.

## Critical invariants
- The repository is public: keep internal links, hostnames and customer data out of code, docs, issues, commits and PRs, because anyone can read them.

<important if="you add an operation">
- Only what a QDAC alone can do belongs here; anything a second backend would want goes to the core `qprogram`, so every backend gets it.
</important>

<important if="you add a runtime dependency">
- `qprogram` stays the only runtime dependency, because a vendor SDK belongs in the platform library that drives the instrument.
</important>

<important if="you add or change an operation or a builder method">
- Nothing here touches an instrument or converts a value: the DSL carries numbers unchanged and the platform converts them, because the chassis model, wiring and calibration live there.
</important>

<important if="you change an existing operation's fields, meaning or `.qp` wire form">
- A change to an operation's meaning on the wire is a major bump with a migration registered through `qp.register_vendor_migration("qdac", ...)`, because users' `.qp` files must keep loading with their meaning.
</important>

<important if="you edit `pyproject.toml` or rename the package">
- The `qprogram.vendors` entry point in `pyproject.toml` keeps naming `qprogram_qdac`, because `qprogram.loads` imports the package through it when a file says `require qdac`.
</important>

<important if="you touch numeric code, units, golden values or tolerances">
- Units: `set_offset` offsets are V; `play` dwell is integer µs (at least 2); `play` delay and `set_trigger` duration are float s; a waveform's own duration stays integer ns (core DSL). The full convention and its exceptions are in CODING_STANDARDS.md additions.
- Every numeric change ships with the before-and-after evidence REVIEW.md asks for.
</important>

## Branches and PRs

<important if="you create a branch, open or title a PR, or merge one">
Decision 2 (Qilimanjaro Software branch conventions), opted in through towncrier (`[tool.towncrier]` in `pyproject.toml`). TODO(human): confirm the opt-in with the maintainers.
- Branch from `main`, named after the ticket. QHC work: branch `qhc-####-<topic>`, PR title `[QHC-####] Name`, with the Linear ticket linked (PR #8). TODO(human): agree the pattern for work that starts from a GitHub issue; PRs #1 to #6 used descriptive names and no ticket key.
- Experiments: `exp/<topic>`, no ticket key. Deliveries: `delivery/<project>-<topic>`.
- One concept per PR. The repository merges by squash only.
</important>

<important if="you make a change a caller would notice">
- A PR with a change a caller would notice adds `changelog/<PR number>.<type>.md`; before the PR has a number, name it `+<topic>.<type>.md` and rename it later. Types are in `[tool.towncrier]`.
</important>

<important if="you change the package version or cut a release">
- Feature PRs leave the version alone. A release is its own PR from `main` (`release-0.3.0`), then a GitHub Release with a bare `X.Y.Z` tag (`docs/developer/contributing.md`, "Releasing").
</important>

## Agent workflow
- Gardener: TODO(human) (owns the environment-change list after each retro)
- Trust rung: 1 (Pair), proposed: the human drives and reads every diff live. The verify command now exists; rung 2 needs a slice run through stages 3-8 without the coach.
- Scratch output (research, specs, evidence) goes to `.agents/artifacts/`, which is gitignored.

## Agent skills

<important if="you read, file, label or triage issues">
### Issue tracker
Mixed, to be confirmed: GitHub Issues is the public intake and backlog; Linear team QHC holds the work QHC picks up. See `docs/agents/issue-tracker.md`.
### Triage labels
The five roles mapped onto GitHub's default labels; three still need creating. See `docs/agents/triage-labels.md`.
</important>

<important if="you name a concept or record a decision">
### Domain docs
Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
</important>

## Completion
Work is ready for review when the verify command passes and its output is attached to the PR. The verify command runs the gates of the workflows that run on pull requests.
