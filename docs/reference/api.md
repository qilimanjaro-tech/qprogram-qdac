# API reference

Auto-generated reference for the `qprogram_qdac` package: one program class,
one mixin, one namespace, four operations, the trigger-position literal, and
one capability profile. Names are linked into the guides where a narrative
helps.

## Program entry points

Two ways to get a `QProgram` with a typed `.qdac` namespace. Use the
pre-combined class when qdac is the only vendor extension in play, and the
mixin when a platform combines several vendor extensions on one program class.

Neither is needed at runtime: importing `qprogram_qdac` registers the namespace
on the base `qprogram.QProgram`, so `program.qdac.set_offset(...)` resolves
through the dynamic vendor lookup on any program. The typed surface is what
editors and type checkers read.

::: qprogram_qdac.QProgram
    options:
      show_root_full_path: false

::: qprogram_qdac.QdacMixin
    options:
      show_root_full_path: false
      members:
        - qdac

## Vendor namespace

`QdacNamespace` is the builder surface. Each method constructs one operation
and appends it to the program's active block.

::: qprogram_qdac.QdacNamespace
    options:
      show_root_full_path: false
      members:
        - wait_trigger
        - set_trigger
        - set_offset
        - play

## Operations

The AST nodes the namespace appends. They are data plus introspection: typed
attributes, and a `required_capabilities` that reports the tokens a platform
must declare to run the node. See
[Capabilities and profiles](../guide/capabilities.md) for how those tokens are
checked.

::: qprogram_qdac.WaitTrigger
    options:
      show_root_full_path: false

::: qprogram_qdac.SetTrigger
    options:
      show_root_full_path: false

::: qprogram_qdac.SetOffset
    options:
      show_root_full_path: false

::: qprogram_qdac.Play
    options:
      show_root_full_path: false

::: qprogram_qdac.operations.TriggerPosition
    options:
      show_root_full_path: false

## Capability profile

The bundle a platform attaches to every qdac-driven bus: the four vendor
tokens, the single-channel waveforms the engine can render, the one
waveform-engine limit, and the two predicates that turn a swept parameter
into a host-side loop and an empty trigger-output set into an error.

::: qprogram_qdac.QDAC_DEFAULT_V1
    options:
      show_root_full_path: false
