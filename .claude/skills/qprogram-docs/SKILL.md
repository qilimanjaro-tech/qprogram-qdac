---
name: qprogram-docs
description: Write or edit documentation in this repo. Use when touching docs/, the README, or a public docstring, and whenever a change to the qdac extension needs its documentation brought along. Carries the house writing style, the conventions of each documentation surface, the change checklist, and the docs checker.
---

# Writing QDevil QDAC extension documentation

This package documents one vendor extension. The language it extends is
documented in the core `qprogram` repository, and these pages should point
there rather than restate it. A page that re-explains the AST, the capability
protocol, or the `.qp` format will drift out of step with the copy that owns
it.

Documentation here is held to the same standard as the code: correct first,
readable second.

## Check the claim before you write it

The code is the authority on what this extension does. Read the implementation
before writing about its details, and verify operation names, arguments, and
capability tokens against `src/` rather than from memory.

Two things are easy to get wrong and worth checking every time. The DSL surface
and the hardware surface can use different units, so say which one a number is
in. And an operation's real-time or host-side classification comes from the
profile, not from intuition, so read `profiles.py` before claiming either.

## The change checklist

A change to the extension is not finished when the code is. These move
together:

1. The code in `src/`.
2. The tests, including the registration and profile tests.
3. `docs/guide/operations.md` for a new or changed operation.
4. `docs/guide/capabilities.md` when the tokens or the profile change.
5. `docs/developer/lowering.md` when a compiler author needs to know how the
   operation reaches hardware.
6. The docstrings of anything in `docs/reference/api.md`, which is generated
   from them.

A new operation is also a minor version bump of the vendor protocol. Say so in
the docs that mention the version.

## Where each kind of documentation lives

| Surface | What it is | Read before editing |
|---|---|---|
| `docs/` | The user-facing site, built with zensical and deployed by CI. | [surfaces.md](references/surfaces.md#the-documentation-site) |
| `README.md` | The front page and the PyPI long description. | [surfaces.md](references/surfaces.md#the-readme) |
| Docstrings in `src/` | Google style, rendered into the API reference by mkdocstrings. | [surfaces.md](references/surfaces.md#docstrings) |

## House style

The full rules are in [style.md](references/style.md), and they are the same
rules the core repository uses. Read that file before writing prose. The short
version: write the way an experienced engineer explains something to a
colleague, do not use em dashes, avoid the vocabulary that marks generated
text, prefer connected paragraphs to bullet fragments, keep headings in
sentence case, and cut anything that sounds promotional before handing it over.

## Running the checker

```bash
uv run python .claude/skills/qprogram-docs/scripts/check_docs.py docs
```

Broken examples, broken links, and broken nav entries are errors. Style
findings are warnings; `--strict` promotes them.

This repo's examples that show composition with the `qblox` extension
report two warnings, because `qblox` is not installed in this environment.
That describes the machine, not the page. `--strict` already leaves `qp-vendor`
alone; the matching `stale-api` warning on `program.qblox` is the same
situation.

A snippet that is deliberately not valid, such as the hypothetical operation in
`developer/lowering.md`, is exempted with an HTML comment above the fence:

```markdown
<!-- check: skip -->
```

CI also runs `zensical build --strict`, which fails on an unresolved
mkdocstrings cross-reference. Build locally before opening a PR that touches
docstrings.
