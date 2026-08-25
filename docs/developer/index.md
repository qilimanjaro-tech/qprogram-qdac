# Developer guide

These pages document the internals: what you need to drive real hardware from
a QDAC program, and what you need to change this package.

| Topic                                 | What you find there                                                                                            |
|---------------------------------------|----------------------------------------------------------------------------------------------------------------|
| [Lowering onto hardware](lowering.md) | The module layout, the registration hooks, what a platform does with each operation, and how to add a new one. |
| [Contributing](contributing.md)       | The uv workflow, the lint and test gate, style rules, and the checklist for a change.                          |

The [User guide](../guide/index.md) covers the same operations from the caller's
side, and the [API reference](../reference/api.md) is generated from the
docstrings under `src/`, so the code and the reference move together.

This package is only the QDAC half. The AST, the `.qp` format, the
capability protocol, and the reference executor all live in the core DSL.
Two of its developer pages are the background for everything here:
[building a vendor extension](https://qilimanjaro-tech.github.io/qprogram/developer/vendor-extensions.html)
is the template this package follows, and
[capability protocol internals](https://qilimanjaro-tech.github.io/qprogram/developer/capability-protocol.html)
is the normative account of tokens, slots and predicates.
