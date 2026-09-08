# User guide

Three pages, in the order you usually need them.

| Topic                                              | What it covers                                                                                     |
|----------------------------------------------------|----------------------------------------------------------------------------------------------------|
| [Operations](operations.md)                        | `set_offset`, `set_trigger`, `wait_trigger`, `play`: arguments, defaults, and what the hardware does. |
| [Capabilities and profiles](capabilities.md)       | `qdac-default-v1`, host-side dispatch for swept parameters, single-channel waveforms, diagnostics.  |
| [Saving and loading](serialization.md)             | The `.qp` wire form of each operation, `require qdac`, and vendor auto-activation on load.          |

Everything the core DSL offers still applies on a QDAC bus: variables and expressions, sweeps and their sources, blocks, fragments, and the `.qp` round trip. Those are documented in the [core documentation](https://qilimanjaro-tech.github.io/qprogram/); the pages here cover only what this package adds.

If you are writing the platform that drives a QDAC rather than a program that targets one, start at [Lowering onto hardware](../developer/lowering.md). For the generated signatures and docstrings, see the [API reference](../reference/api.md).
