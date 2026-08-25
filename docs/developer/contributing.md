# Contributing

The short version: open a small pull request, run the linter and the tests,
write the docs for anything that changes user-visible behavior.

## Before you start

Skim two things first.

1. **[Lowering onto hardware](lowering.md).** It explains the five modules, the
   registration hooks, and what a platform does with each operation. Almost
   every change touches one of those.
2. **The core DSL's developer guide**, in particular
   [building a vendor extension](https://qilimanjaro-tech.github.io/qprogram/developer/vendor-extensions.html),
   the template this package follows, and
   [capability protocol internals](https://qilimanjaro-tech.github.io/qprogram/developer/capability-protocol.html),
   the normative account of tokens, slots and predicates. The AST, the
   validator, and the `.qp` format live there too. A change to this package that
   needs a core change is usually a core issue instead.

Then decide which repository the change belongs in. An operation only a QDAC can
do belongs here. Anything a second backend would also want belongs in the core,
so every backend gets it.

## The core DSL is a sibling checkout

`[tool.uv.sources]` points `qprogram` at `../qprogram`, so the core DSL has to
sit next to this repository:

```bash
git clone https://github.com/qilimanjaro-tech/qprogram
git clone https://github.com/qilimanjaro-tech/qprogram-qdac
cd qprogram-qdac
```

```
parent/
├── qprogram/          # the core DSL, editable
└── qprogram-qdac/     # this repository
```

The published wheel declares a plain `qprogram>=0.1.0` dependency. The
`[tool.uv.sources]` table only steers local and CI resolution, and CI checks the
core out as a sibling the same way, so an installing user always resolves the
core from the index.

## Development workflow

1. **Install the package.**

   ```bash
   uv sync --group dev
   ```

2. **Install the docs environment** (optional, only if you change docs).

   ```bash
   uv sync --group docs
   uv run --group docs zensical serve
   ```

   `mkdocstrings` imports the package to render the API reference, so the docs
   build needs the project installed, not just the docs tooling.

3. **Make your change.**

4. **Lint and format.**

   ```bash
   uv run ruff check .
   uv run ruff format .
   ```

5. **Type-check.**

   ```bash
   uv run ty check
   ```

6. **Run the tests.**

   ```bash
   uv run pytest
   uv run pytest --cov=qprogram_qdac    # check coverage on touched files
   ```

7. **Update the docs.** Anything user-visible needs an entry in the relevant
   guide page and, for a new class or method, an entry in
   [`docs/reference/api.md`](../reference/api.md), whose `members:` lists are
   explicit.

8. **Open the pull request.** The workflows under `.github/workflows/` run on
   it. `tests.yml` runs the suite on Python 3.11 and 3.14 for a pull request,
   across 3.11 through 3.14 on a push to `main`, and uploads coverage from the
   3.13 job. `code_quality.yml` runs `ruff check` and `ruff format --diff` once
   on 3.13, then `ty check` once per supported version. `docs.yml` builds this
   site, and deploys it on a push to `main`. Each of the three checks the core DSL
   out as a sibling directory first.

## What "small PR" means

One concept per pull request. A new operation plus a new predicate plus a
serialization fix is three pull requests. Each one is easier to review, easier
to revert, and easier to bisect against.

## The checklist for a new operation

All five code edits are listed in
[Adding an operation](lowering.md#adding-an-operation). A complete pull request
carries four kinds of change:

| Kind              | What it means                                                                                                                    |
|-------------------|----------------------------------------------------------------------------------------------------------------------------------|
| **Code**          | The node in `operations.py`, the method on `QdacNamespace`, the token in `profiles.py` twice, the registration in `__init__.py`.   |
| **Tests**         | One test per module in `tests/`: operations, namespace, serialization, registration, profile.                                      |
| **Docs**          | The operation's row and section in the user guide, its wire form in the serialization page, and anything the platform must know in [Lowering onto hardware](lowering.md). |
| **API reference** | The class and the namespace method added to the `members:` lists in `docs/reference/api.md`.                                       |

Adding an operation is a minor version bump of the package, which is also the
vendor protocol version in the `require qdac <major>.<minor>` header. Removing
or renaming one, or changing what it means on the wire, is a major bump.

## Style notes

These are the rules the project enforces; they are not exhaustive. All of them
are configured in `pyproject.toml`.

- **Ruff with `preview = true` and `select = ["ALL"]`**, minus a curated ignore
  list written as rule *names* rather than codes, so the reason for each
  exemption reads off the config. Suppression comments use the same form:
  `# ruff: ignore[import-outside-top-level]`, never a numeric code. Line length
  is 120 and the formatter owns it. Expect the linter to push back on most
  external code.
- **Docstrings are enforced.** Preview mode means both the `D` and the `DOC`
  families run, under the Google convention. Every parameter gets a
  `name (type): Description.` entry, with the parenthesized type as house style
  even though the signature is annotated. A non-`None` return needs a `Returns:`
  section unless the summary line already opens with the word "Return", and
  every exception a caller can observe needs a `Raises:` entry. Constructor
  arguments are documented on the **class** docstring, since
  `merge_init_into_class` is on and `undocumented-public-init` is ignored.
  `Attributes:` is for a value object whose fields are the interface and are not
  all constructor arguments.
- **Cross-references are Markdown, not Sphinx roles.** Write
  `` [`SetOffset`][qprogram_qdac.SetOffset] `` for a target this site documents, and
  `` [`Expression`][qprogram.Expression] `` for one the core DSL documents:
  `zensical.toml` loads that project's published `objects.inv` as an
  `inventories` entry, so a core type resolves to its page on that site. Plain
  `` `Expression` `` is for anything neither site renders, such as a builtin or
  a stdlib name. A Sphinx role such as `` :class:`~qprogram.Expression` ``
  would reach the page as literal text, since mkdocstrings reads a docstring as
  Markdown and has no reStructuredText reader;
  `tests/test_docstring_style.py` fails the suite on one. The docs build runs
  with `--strict`, so a cross-reference neither site can resolve fails CI as
  well.
- **Every file carries the Apache header**, the standard 13-line notice with
  `Copyright 2026 Qilimanjaro Quantum Tech`, above the module docstring. Ruff's
  `missing-copyright-notice` rule fails the lint on a file without it. Tests
  included.
- **Type hints everywhere.** `ty` is in the dev group and checks `src`, and CI
  runs it once per supported Python version.
- **Function-style tests.** No test classes. Use fixtures from
  `tests/conftest.py` and parametrization. Tests are exempt from the `ANN`,
  `D`, and `DOC` families, so a test needs no docstring, but one explaining
  *why* a case exists is worth writing.
- **Two-space indentation in `.qp` fixtures.** That is what the writer emits.
- **No new runtime dependencies.** This package depends on `qprogram` and
  nothing else, and that is on purpose. A vendor SDK belongs in the platform
  library that drives the instrument, not in the package that describes it.

## What goes where

| Change kind                        | Where it lands                                                        |
|------------------------------------|-----------------------------------------------------------------------|
| New operation                       | `src/qprogram_qdac/operations.py` plus the four other edits.          |
| New method on the namespace         | `src/qprogram_qdac/namespace.py`.                                    |
| New capability token or predicate   | `src/qprogram_qdac/profiles.py`.                                     |
| New limit                           | `src/qprogram_qdac/profiles.py`, in `QDAC_DEFAULT_V1.limits`.         |
| New profile bundle                  | `src/qprogram_qdac/profiles.py`, registered from `__init__.py`.       |
| Registration or the typed program   | `src/qprogram_qdac/__init__.py`.                                     |
| Docs                                | `docs/`; the nav lives in `zensical.toml`.                            |
| Anything about the AST or `.qp`     | The core DSL, not here.                                               |

## Commit messages

Short, imperative, explanatory. The body matters more than the title: explain
*why*, not *what*. The history in `git log` is a good template.

## License and attribution

`qprogram-qdac` is licensed under the Apache License, Version 2.0. The full text
is in the `LICENSE` file at the repository root, and every source file carries
the matching 13-line header. By opening a pull request you agree to license your
contribution under the same terms.

## Where to ask

- **Bug reports and feature requests.** Open a GitHub issue; the templates are
  short on purpose. Include a minimal program and, for anything about the file
  format, its `.qp` text. A problem that reproduces without importing
  `qprogram_qdac` belongs in the core repository.
- **Design discussion.** Open an issue naming the affected code, the behavior
  you expect, and the guide page that documents it.

Pull requests with a clear scope and tests are the fastest path to a merge.
