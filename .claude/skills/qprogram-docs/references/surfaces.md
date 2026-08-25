# Documentation surfaces

Three places in this repo hold prose, and they do not share conventions.

## The documentation site

`docs/` is the user-facing site, built with **zensical**, not mkdocs,
configured in `zensical.toml`:

```bash
uv sync --group docs --all-extras
uv run zensical serve      # or: uv run zensical build --strict
```

mkdocstrings imports the package to render the API reference, so the project
and its extras have to be installed, not just the docs tooling.
`.github/workflows/docs.yml` does the same and deploys to GitHub Pages from
`main`.

The tree is smaller than the core repository's: `index.md`,
`getting-started.md`, a `guide/` covering the operations, the capability
profile and serialization, a `reference/` holding the generated API, and a
`developer/` covering lowering onto hardware and contributing.

Where a change lands depends on who needs it. A new or changed operation goes
in `guide/operations.md`. Token or profile changes go in
`guide/capabilities.md`. Anything a compiler author needs in order to lower an
operation onto real hardware goes in `developer/lowering.md`.

The nav in `zensical.toml` is explicit and is the only way a page becomes
reachable. Adding a file to `docs/` does not put it in the site; the checker
reports pages that exist on disk but are absent from the nav.

`reference/api.md` is generated from mkdocstrings directives, one per public
symbol. Add a directive for a new symbol rather than hand-writing its
signature.

## The README

`README.md` is the repository front page and, through `readme` in
`pyproject.toml`, the PyPI long description. Relative links do not resolve on
PyPI, so link to the published docs site for anything a package page needs to
reach.

Keep it to what someone needs before deciding to use the package: what the
extension adds, how to install it, one worked example, and where to read more.

## Docstrings

Google convention, enforced by ruff's pydocstyle rules. `ruff format`
reformats code inside docstrings, so any example in one has to be valid Python.

Docstrings are rendered into the API reference, which makes them part of the
site. Cross-references use the mkdocstrings Markdown form, with the display
text in backticks and the target as a full dotted path:

```
[`QProgram`][qprogram.QProgram]
```

Sphinx roles (`` :class:`~qprogram.QProgram` ``) do not resolve and render as
literal text. They were converted across the package and should not come back.
An unresolved target fails the CI docs build.

## What belongs in the core repository instead

The language, the `.qp` format, the capability protocol, and the validator are
documented in `qprogram`. Link to those pages rather than restating them: a
second copy of an explanation is a second copy to keep true, and this one will
lose.
