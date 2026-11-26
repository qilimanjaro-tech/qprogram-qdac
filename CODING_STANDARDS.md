# qprogram-qdac coding standards

Shared core v0.2 (Qilimanjaro Software), a draft until the software leads agree it. Copied verbatim, followed by qprogram-qdac additions. Mechanical rules live in the tools configured in `pyproject.toml` and in CI; this file holds the judgement they cannot make. The review contract is `REVIEW.md`; findings cite the section they apply.

## Tests

Tests are behaviour tests: they drive the public interface at an agreed seam and assert what a caller observes.

- **Seams.** Test at the seams listed in the additions below. A new seam is named in the PR description before tests target it.
- **Observable outcomes.** Assert returned values, raised errors, emitted programs and waveforms, and results read back through the public reader.
- **Independent expected values.** Take expected values from a literal, a worked example, the specification, a published reference or a hardware-validated fixture, never recomputed the way the code computes them.
- **Boundary mocks.** Mock instrument drivers and hardware execution, network, databases, the file system when needed, time and randomness. The package's own classes and functions run for real.
- **Public reach.** When a behaviour is visible only through a `_private` name, add a public accessor or move the test to the seam above.
- **Regressions.** A bug fix starts with a test that fails on the bug.
- **Coverage is evidence.** A line counts as covered when a behaviour test exercises it. Hardware-only code goes in the coverage `omit` list with a reason.

## Code

- **Design.** Prefer deep modules: a small interface over a lot of behaviour. Name things with the terms in `GLOSSARY.md`; a new concept gets a glossary entry first.
- **Units.** Physical quantities carry their unit in the name, a type alias or the docstring (Hz, ns, V, rad, dBm), fixtures included, in the convention the additions state.
- **Suppressions.** Every suppression (`# noqa`, `# type: ignore`, `# ty: ignore`, `# pragma: no cover`, a coverage `omit`) names its rule code and a one-line reason.
- **Comments.** Explain why. A comment that excuses a workaround becomes a type, a lint or a test.
- **Dependencies.** A dependency on another Qilimanjaro package names the released version that carries the needed behaviour.
- **Compatibility.** Public API changes go through a deprecation release unless the PR links an accepted decision to break compatibility.

## Change hygiene

- User-facing changes add a towncrier fragment in `changes/`, in repos that use towncrier.
- Interface or architecture decisions link their decision record; proposals stay labelled as proposals until accepted.

## qprogram-qdac additions

- **Seams:** the builder, `program.qdac.<operation>()`, asserting the operation node it appends (`tests/test_namespace.py`, `tests/test_mixin.py`); the operation nodes' attributes, `required_capabilities()` and equality (`tests/test_operations.py`); the `.qp` text through `qprogram.dumps` and `qprogram.loads` (`tests/test_serialization.py`); `qprogram.validate` and `qprogram.explain` against capabilities built from `qdac-default-v1`, asserting diagnostic codes (`tests/test_profile.py`); and what importing the package registers (`tests/test_registration.py`).
- **Boundary mocks:** none beyond the core. Nothing in this package touches an instrument (`docs/developer/lowering.md`), and the core `qprogram` runs for real in every test.
- **Units:** the DSL carries QDAC values unchanged and the platform converts them (`docs/developer/lowering.md`, "Units at a glance"). `SetOffset.offset` is V (`src/qprogram_qdac/operations.py:148`). `Play.dwell` is an integer number of µs, at least 2 (`src/qprogram_qdac/operations.py:177`, `_MIN_DWELL_US` at `src/qprogram_qdac/profiles.py:160`). `Play.delay` and `SetTrigger.duration` are float s (`src/qprogram_qdac/operations.py:180`, `src/qprogram_qdac/operations.py:107`). The exception is a waveform's own `duration`, which stays integer ns because the core DSL defines it (`src/qprogram_qdac/operations.py:24-27`). The package has no frequencies or phases. The `.qp` text writes the same numbers (`tests/test_serialization.py:85`, `tests/test_serialization.py:94`).
- **Coverage:** no `fail_under` in `pyproject.toml`; the suite covers 100% of lines and branches today. TODO(human): agree a coverage floor.
- **Tooling:** suppressions name the ruff rule by its name, not its code (`# ruff: ignore[import-outside-top-level]`), the way `pyproject.toml` lists its ignores, so the reason reads off the comment.
- **Changelog:** fragments go in `changelog/`, the `[tool.towncrier]` directory, named `<PR number>.<type>.md`. Internal refactors, test-only changes and docs corrections need none (`docs/developer/contributing.md`).
- **Dependencies:** `qprogram` is the only runtime dependency, because a vendor SDK belongs in the platform library that drives the instrument (`docs/developer/contributing.md`).
- **Tests:** function-style, no test classes, fixtures from `tests/conftest.py`. A `.qp` fixture takes its header from `tests/_header.py`, never a literal version, so it keeps loading across a release of either library.
