# Lowering onto hardware

This page is for the person writing the platform: the code that takes a validated `QProgram` and drives a QDAC chassis. It says what each AST node means, which conversions the DSL leaves to you, how a swept argument has to be evaluated, and what the capability profile lets a platform accept.

Nothing in `qprogram-qdac` touches an instrument. The package builds typed AST nodes, serializes them, and declares what a QDAC channel can do. The driver calls are yours.

## The five modules

| Module          | What it owns                                                                                                          |
|-----------------|-----------------------------------------------------------------------------------------------------------------------|
| `operations.py` | The four AST node classes, the `TriggerPosition` literal, and each node's `required_capabilities()`.                    |
| `namespace.py`  | `QdacNamespace`: the typed `program.qdac.*` methods that build a node and append it to the program's active block.      |
| `mixin.py`      | `QdacMixin`: the typed `.qdac` property, for editors and type-checkers.                                                 |
| `profiles.py`   | The vendor capability tokens, the two predicates, and the `qdac-default-v1` profile.                                    |
| `__init__.py`   | The registration calls, the protocol version, and `QProgram` pre-combined with the mixin.                               |

The dependency direction is one way. Every module imports from `qprogram`; `qprogram` imports nothing from here.

## What runs at import

Importing `qprogram_qdac` is the activation step. Five things happen, in this order:

1. **Capability tokens.** `__init__.py` imports `qprogram_qdac.profiles`, and that module calls `register_capability_tokens` at import. Registration comes before the `Profile` is built, because `Profile.__post_init__` rejects a token that is not in the registry.
2. **Runtime namespace.** `QProgram.register_vendor("qdac", QdacNamespace)` makes `program.qdac` resolve on any program, mixin or not. The base class resolves it through `__getattr__` and caches the namespace on the instance.
3. **Protocol version.** `register_vendor_version("qdac", __version__)`, with the version read from installed package metadata. This is what the `.qp` header's `require qdac <major>.<minor>` is checked against.
4. **Operations.** One `register_vendor_operation("qdac", <name>, <cls>)` per node class. The writer looks up an instance's class to find the `(vendor, name)` pair; the parser reverses the lookup.
5. **Profile.** `register_profile(QDAC_DEFAULT_V1)`, so `CompilerCapabilities.from_profile("qdac-default-v1")` resolves.

Those steps are the vendor hooks in action: the runtime namespace is step 2, the serialization registry is steps 3 and 4, and the capability protocol is steps 1 and 5. The typed mixin is the one hook with no registration call, being a plain class the pre-combined `QProgram` inherits from.

```python
import qprogram as qp
import qprogram_qdac  # the activation step
from qprogram.protocol import resolve_profile

program = qp.QProgram()  # the base class, no mixin
program.qdac.set_offset("flux_q0", 0.1)

print(type(program).__name__, type(program.qdac).__name__)
print(qprogram_qdac.__version__)
print(resolve_profile("qdac-default-v1").version)
print(qp.dumps(program).splitlines()[2])
```

```
QProgram QdacNamespace
0.1.0
(0, 1, 0)
require qdac 0.1
```

Loading a `.qp` file does not need that import to have happened first. The `[project.entry-points."qprogram.vendors"]` table in `pyproject.toml` maps the vendor name to this module, so `qp.loads` on a file carrying `require qdac 0.1` imports the package on demand:

```python
import qprogram as qp

text = '#!QProgram 0.2\nrequire qdac 0.1\nbody:\n  qdac.set_offset "flux_q0" 0.42\n'
program = qp.loads(text)
print(type(program.body.elements[0]).__module__)
```

```
qprogram_qdac.operations
```

## The four operations

Every QDAC operation carries a `bus` attribute, which is one QDAC channel. `Operation.BUS_ATTRS` defaults to `("bus",)`, so bus introspection, `rebind`, and per-bus capability routing all work without any declaration. The nodes hold their arguments verbatim. The numbers reach your driver exactly as the user wrote them.

### `qdac.set_offset`

```
SetOffset(bus, offset)
qdac.set_offset "flux_q0" 0.42
```

Hold a DC level on the channel. The platform writes the value and leaves it there: there is no duration and no end, so the level stands until another operation changes it or the program finishes. Program order inside the block is the order of the writes.

`offset` is in volts. It may also be any `Expression`, which is the swept form covered [below](#swept-arguments-evaluate-per-iteration).

Not done for you: no clamping to the channel's output range, no conversion to DAC codes, no compensation for an external divider or attenuator, no slew limiting, and no scaling from millivolts. Range-check the value and decide your own policy for one that is out of range.

### `qdac.play`

```
Play(bus, waveform, dwell=1, delay=0, repetitions=1, stepped=False)
qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000) dwell=200
```

Upload an envelope to the channel's waveform engine and run it. Sample the envelope with `waveform.envelope(resolution=1)`, which returns one sample per nanosecond of `waveform.get_duration()`, then program the engine with `dwell`, `delay`, `repetitions`, and `stepped`.

The four engine arguments are pass-through values:

| Argument      | Meaning                                                     |
|---------------|-------------------------------------------------------------|
| `dwell`       | How long the engine holds each sample, in nanoseconds.       |
| `delay`       | Nanoseconds between the sequence start and the first sample. |
| `repetitions` | How many times the engine repeats the envelope.              |
| `stepped`     | Discrete steps when `True`, interpolated output when `False`.|

Four things the DSL deliberately does not do:

- **`dwell` is not reconciled with the envelope's own duration.** The envelope is a list of samples; `dwell` is how long each one is held. `Ramp(0.0, 1.0, 1000)` is 1000 samples, so at `dwell=200` the sequence lasts 200 µs, two hundred times the waveform's nominal 1000 ns. Nothing warns about that. Decide whether you resample the envelope down to the point count your engine can store, or reject the pair.
- **Amplitude is dimensionless.** An envelope sample is whatever the waveform's amplitude arguments say, so `Ramp(0.0, 1.0, 1000)` peaks at `1.0`. Mapping that onto full-scale volts, and applying any per-channel gain, is the platform's job.
- **No granularity or floor checks.** `dwell` and `delay` are nanosecond integers, never rounded to the engine's clock granularity and never checked against the profile's `min_dwell_ns` (see [Limits](#limits-are-declared-not-enforced)). `repetitions` is not checked against the engine's memory depth or against any total-duration budget.
- **The waveform's channel kind is not enforced at build time.** `Play` always reports `waveform.single` alongside the per-class token, so the token set alone does not prove the envelope is real-valued. An IQ waveform reaches the node, and validation catches it only because its per-class token is missing from the profile:

```python
import qprogram as qp
from qprogram.protocol import BusCapabilities, CompilerCapabilities, PlatformCapabilities
from qprogram.waveforms import IQDrag
from qprogram_qdac import QProgram

qdac_caps = CompilerCapabilities.from_profile("qdac-default-v1")
platform_caps = CompilerCapabilities.from_profile("qprogram-base-v1")

caps = PlatformCapabilities(
    bus={},
    platform=BusCapabilities(rt=platform_caps, host=platform_caps),
    default_bus_profile=BusCapabilities(rt=None, host=qdac_caps),
)

program = QProgram()
program.qdac.play("flux_q0", IQDrag(amplitude=0.5, duration=100, sigma=25, beta=0.1))

print(sorted(program.body.elements[0].required_capabilities()))
for diagnostic in qp.validate(program, caps)[0]:
    print(diagnostic.severity, diagnostic.code, diagnostic.message)
```

```
['vendor.qdac.play', 'waveform.iq_drag', 'waveform.single']
error missing-capability 'Play' requires capability 'waveform.iq_drag' which is not supported by 'qdac-default-v1' (host)
```

A waveform can also arrive as a name rather than an object, which contributes no waveform token at all and so validates clean. Resolve names against a `WaveformLibrary` before lowering, and treat a `str` in `Play.waveform` as a program that is not ready to compile:

```python
from qprogram import BusSchema, WaveformLibrary, dumps
from qprogram.waveforms import Ramp
from qprogram_qdac import QProgram

schema = BusSchema.flux_tunable_transmon()
program = QProgram(schema=schema)
program.qdac.set_offset(schema.q[0].flux, 0.3)
program.qdac.play(schema.q[0].flux, "bias_ramp")

library = WaveformLibrary()
library.set("bias_ramp", Ramp(0.0, 0.5, 400), element="q", kind="flux")
bound = program.with_waveforms(library)
print(type(bound.body.elements[1].waveform).__name__)

ported = bound.rebind(elements={("q", 0): ("q", 1)})
print(sorted(str(bus) for bus in ported.body.buses()))
print(dumps(ported).splitlines()[-1])
```

```
Ramp
['q1/flux']
  qdac.play q[1].flux Ramp(from_amplitude=0.0, to_amplitude=0.5, duration=400)
```

Both transforms work on QDAC nodes for the same reason: `Play` declares `WAVEFORM_ATTRS = ("waveform",)`, and the default `BUS_ATTRS` covers `bus`.

### `qdac.set_trigger`

```
SetTrigger(bus, duration, position="start", outputs=())
qdac.set_trigger "flux_q0" 20 position="step" outputs=[1, 2]
```

Arm chassis trigger outputs to fire at a sequence event. The platform routes each index in `outputs` on the internal trigger bus and holds it active for `duration` nanoseconds.

| `position`   | The engine fires                            |
|--------------|---------------------------------------------|
| `"start"`    | when the sequence begins.                    |
| `"step"`     | at the start of every step.                  |
| `"end"`      | when the sequence finishes.                  |
| `"end_step"` | at the end of every step.                    |

`outputs` accepts any iterable of integers and is stored as a sorted tuple with duplicates dropped, so `{3, 1, 2}` and `[1, 2, 3]` are the same node, hash the same, and emit the same `outputs=[1, 2, 3]` line.

Not done for you: the output indices are chassis-defined and are not bounds-checked, `duration` is not rounded to the trigger bus's granularity, and a step-relative `position` on a sequence that is not `stepped` is accepted. The one case the package does reject is an empty `outputs`, through a profile predicate (see [What the profile constrains](#what-the-profile-constrains)).

### `qdac.wait_trigger`

```
WaitTrigger(bus, port)
qdac.wait_trigger "flux_q0" 1
```

Halt that channel's sequencer until an edge arrives on trigger input `port`. Nothing is emitted while it waits. This is the synchronization point with another instrument, whose own sequencer fires the trigger.

Not done for you: there is no timeout, no bounds check on the port, and no deadlock analysis. A program that waits for a trigger nobody sends is a valid program, so a real platform wants its own timeout around the wait.

### Units at a glance

| Attribute             | Unit                   | What the DSL checks                     |
|-----------------------|------------------------|-----------------------------------------|
| `SetOffset.offset`    | volts                  | nothing                                 |
| `Play.dwell`          | nanoseconds per sample | nothing                                 |
| `Play.delay`          | nanoseconds            | nothing                                 |
| `Play.repetitions`    | count                  | nothing                                 |
| `SetTrigger.duration` | nanoseconds            | nothing                                 |
| `SetTrigger.outputs`  | chassis output index    | sorted and deduplicated; empty rejected |
| `WaitTrigger.port`    | chassis input index     | nothing                                 |

Carrying the numbers unchanged is the point. Every conversion, clamp, and rounding decision belongs to the platform, where the chassis model, the wiring, and the calibration live.

## Swept arguments evaluate per iteration

`SetOffset.offset`, and any waveform parameter, accepts an `Expression`. The node stores the expression tree, not a number. Evaluating it once while compiling is the mistake to avoid: the value is only defined after the enclosing sweep binds its variable.

The points come from the loop's `source`, the variable to bind them to is `Sweep.variable`, and `Expression.evaluate_or_raise()` reads whatever is bound at the moment it is called:

```python
from qprogram.sweeps import Range
from qprogram_qdac import QProgram
from qprogram_qdac.operations import SetOffset

program = QProgram()
flux = program.variable("flux")
with program.sweep(flux, Range(0.0, 0.3, 0.1)):
    program.qdac.set_offset("flux_q0", flux * 2)

loop = program.body.elements[0]
print(loop.num_iterations(), loop.source.KIND)
for point in loop.source.values():
    loop.variable.set_value(point)
    for node in loop.elements:
        if isinstance(node, SetOffset):
            print(node.bus, node.offset.evaluate_or_raise())
```

```
4 linear
flux_q0 0.0
flux_q0 0.2
flux_q0 0.4
flux_q0 0.6000000000000001
```

Three facts worth knowing:

- `source.length()` and `source.values()` answer without running the program, so a platform can size its upload plan before the first point.
- `Expression.evaluate()` returns `UNASSIGNED` when nothing is bound. `evaluate_or_raise()` raises instead, which is what you want inside a lowering loop: an unbound variable is a bug, not a value.
- Variables hide in waveform arguments too. `Operation.variables()` descends through expression trees and waveform parameters, so `play(bus, Square(amplitude=amp, duration=100))` reports `amp` the same way `set_offset(bus, amp)` does. When a waveform carries a variable, its envelope cannot be sampled once and reused; resample and re-upload it per iteration.

```python
from qprogram.sweeps import Range
from qprogram.waveforms import Square
from qprogram_qdac import QProgram

program = QProgram()
amp = program.variable("amp")
with program.sweep(amp, Range(0.0, 0.3, 0.1)):
    program.qdac.play("flux_q0", Square(amplitude=amp, duration=100), dwell=200)

play = program.body.elements[0].elements[0]
print(sorted(variable.id for variable in play.variables()))
```

```
['amp']
```

## No FPGA, so every change is a host upload

A QDAC has no FPGA and no real-time sequencer for parameter changes. Every value reaches the instrument over the host link, at millisecond-scale latency. That single hardware fact drives the whole execution model.

`BusCapabilities(rt, host)` splits real-time hardware from host-side orchestration, and either half may be `None`. For a QDAC bus, the honest wiring puts the profile in the `host` half only, which is what this package's own profile tests do. The platform-level slot, which is where blocks and expressions route, comes from the core `qprogram-base-v1` profile and keeps both halves:

```python
import qprogram as qp
from qprogram.protocol import BusCapabilities, CompilerCapabilities, PlatformCapabilities
from qprogram.sweeps import Range
from qprogram_qdac import QProgram

qdac_caps = CompilerCapabilities.from_profile("qdac-default-v1")
platform_caps = CompilerCapabilities.from_profile("qprogram-base-v1")

caps = PlatformCapabilities(
    bus={},
    platform=BusCapabilities(rt=platform_caps, host=platform_caps),
    default_bus_profile=BusCapabilities(rt=None, host=qdac_caps),
)

program = QProgram()
flux = program.variable("flux")
with program.sweep(flux, Range(0.0, 0.3, 0.1)):
    program.qdac.set_offset("flux_q0", flux)

diagnostics, _ = qp.validate(program, caps)
print(diagnostics)
print(qp.explain(program, caps))
```

```
[]
plan — errors: 0 · warnings: 0 · info: 0
body
└─ for flux in Range(start=0.0, stop=0.3, step=0.1):  [host]
   └─ qdac.set_offset "flux_q0" flux                  [host]
```

The operation is host-side because its only slot is the `host` half. The loop is host-side because a block's domain is the intersection of its op-children's domains, and that intersection is `{host}`. No diagnostic is needed to say so.

For a platform, `[host]` on a loop is an instruction: **the loop runs on the host, one upload per iteration**. Concretely, for each point of the sweep: bind the variable, evaluate every expression the body's nodes carry, resample any variable-bearing envelope, upload, arm, run, and read back. The cost per point is the link latency, and it dominates. Nothing folds a QDAC sweep into a hardware loop.

When the same experiment also drives a real-time instrument, the QDAC sweep is the outer loop: the inner real-time program is re-armed inside each iteration, after the bias has settled. `qdac.set_trigger` and `qdac.wait_trigger` are how the two sides hand control to each other within one iteration.

## What the profile constrains

`qdac-default-v1` ships two predicates. Both are plain callables `(node, ctx) -> Iterable[Diagnostic | DomainConstraint]`, run on every visited node in the slot they belong to, and both filter by node type first.

**A QDAC operation with a swept variable forces its loop host-side.** For each loop-bound variable the node references, the predicate yields a `DomainConstraint` excluding `"rt"` on that variable's **binding loop**, found with `ctx.binding_loop_of(var)`. The reason names the operation and the variable. Two rules matter here. A constraint must target a `Block`: pointing one at the operation is reported as `bad-domain-constraint`. And a constraint is soft, meaning "this domain cannot, another one can", which is the difference between it and a `Diagnostic`.

Under the host-only wiring above, the constraint is redundant: consensus has already put the loop in `{host}`, and no `forced-host` diagnostic surfaces because the loop never had `"rt"` to lose. It earns its place on a platform that fills both halves of the bus slot, where it strips `"rt"` back off and reports why:

```python
import qprogram as qp
from qprogram.protocol import BusCapabilities, CompilerCapabilities, PlatformCapabilities
from qprogram.sweeps import Range
from qprogram_qdac import QProgram

qdac_caps = CompilerCapabilities.from_profile("qdac-default-v1")
platform_caps = CompilerCapabilities.from_profile("qprogram-base-v1")

caps = PlatformCapabilities(
    bus={},
    platform=BusCapabilities(rt=platform_caps, host=platform_caps),
    default_bus_profile=BusCapabilities(rt=qdac_caps, host=qdac_caps),
)

program = QProgram()
flux = program.variable("flux")
with program.sweep(flux, Range(0.0, 0.3, 0.1)):
    program.qdac.set_offset("flux_q0", flux)

diagnostics, _ = qp.validate(program, caps)
for diagnostic in diagnostics:
    print(diagnostic.severity, diagnostic.code, diagnostic.message)
print(qp.explain(program, caps))
```

```
warning forced-host Block 'Sweep' falls back to host-side execution: qdac.SetOffset references loop-bound variable 'flux'; qdac has no FPGA, so the loop must dispatch host-side..
plan — errors: 0 · warnings: 1 · info: 0
body
└─ for flux in Range(start=0.0, stop=0.3, step=0.1):  [host]     ~ forced-host: qdac.SetOffset references loop-bound variable 'flux'; qdac has no FPGA, so the loop must dispatch host-side
   └─ qdac.set_offset "flux_q0" flux                  [rt|host]
```

Note the operation still reads `[rt|host]` while the loop reads `[host]`. That is what the constraint does: it lifts the loop, not the operation.

**An empty `outputs` on `set_trigger` is an error.** Arming zero outputs configures a trigger that fires onto nothing, and no domain makes that work, so the predicate yields a `Diagnostic` with `severity="error"` and code `qdac.empty-trigger-outputs`.

A platform reacts to diagnostics by severity, and the convention across the project is: raise `UnsupportedOperationError` on any `error`, surface a `warning` without raising, and pass `info` through as advisory. `validate` never raises on its own.

Site-specific rules do not belong in the vendor profile. Pass them as `extra_predicates` when you materialize the slot, which is also how the limit below gets enforced.

## Limits are declared, not enforced

`qdac-default-v1` declares one limit:

```python
from qprogram_qdac import QDAC_DEFAULT_V1

print(dict(QDAC_DEFAULT_V1.limits))
```

```
{'min_dwell_ns': 100}
```

Below that dwell the waveform engine's output interpolation breaks down. The core validator enforces `max_loop_nesting`, `max_parallel_loops`, and `max_measurements` at the platform slot, and `min_wait_duration_ns` at the bus slot. Every other key, `min_dwell_ns` included, is carried and ignored. So the number is published for tooling and for platforms to read; no `Play` is checked against it.

A platform that wants the check adds its own predicate. `ValidationContext` exposes program-wide data-flow facts, not the slot's limits, so close over the floor you want enforced:

```python
from collections.abc import Iterable

import qprogram as qp
from qprogram.protocol import (
    BusCapabilities,
    CompilerCapabilities,
    Diagnostic,
    DomainConstraint,
    PlatformCapabilities,
    Predicate,
    ValidationContext,
    resolve_profile,
)
from qprogram.waveforms import Ramp
from qprogram_qdac import QProgram
from qprogram_qdac.operations import Play


def dwell_floor(min_dwell_ns: float) -> Predicate:
    """Return a predicate rejecting a qdac.play whose dwell is below min_dwell_ns."""

    def check(node: object, ctx: ValidationContext) -> Iterable[Diagnostic | DomainConstraint]:
        if isinstance(node, Play) and node.dwell < min_dwell_ns:
            yield Diagnostic(
                severity="error",
                code="qdac.dwell-below-minimum",
                message=f"qdac.play dwell={node.dwell} ns is below min_dwell_ns={min_dwell_ns:g}",
                node=node,
            )

    return check


floor = resolve_profile("qdac-default-v1").limits["min_dwell_ns"]
qdac_caps = CompilerCapabilities.from_profile(
    "qdac-default-v1",
    extra_predicates=(dwell_floor(floor),),
)
platform_caps = CompilerCapabilities.from_profile("qprogram-base-v1")
caps = PlatformCapabilities(
    bus={},
    platform=BusCapabilities(rt=platform_caps, host=platform_caps),
    default_bus_profile=BusCapabilities(rt=None, host=qdac_caps),
)

program = QProgram()
program.qdac.play("flux_q0", Ramp(0.0, 1.0, 1000), dwell=10)

for diagnostic in qp.validate(program, caps)[0]:
    print(diagnostic.severity, diagnostic.code, diagnostic.message)
```

```
error qdac.dwell-below-minimum qdac.play dwell=10 ns is below min_dwell_ns=100
```

A device with a tighter floor passes `limit_overrides={"min_dwell_ns": 250}`, so the published number stays truthful, and `dwell_floor(250)`, so the check follows it.

## Adding an operation

Five edits, all inside this package. The core DSL needs no change.

| # | File            | Edit                                                                            |
|---|-----------------|---------------------------------------------------------------------------------|
| 1 | `operations.py` | The `Operation` subclass and its `required_capabilities()`.                       |
| 2 | `namespace.py`  | A typed method on `QdacNamespace` that builds it and calls `self._append`.        |
| 3 | `profiles.py`   | The token, in the `register_capability_tokens` call.                              |
| 4 | `profiles.py`   | The token again, in the `_BUS_OPS` set the profile is built from.                 |
| 5 | `__init__.py`   | The import, the `register_vendor_operation` call, and the `__all__` entry.        |

Steps 3 and 4 are separate because they answer different questions: step 3 makes the token a name the registry knows, and step 4 says a QDAC channel supports it. An operation whose token is registered but absent from the profile fails validation with `missing-capability`. A profile naming a token that was never registered is rejected by `Profile.__post_init__`, at import.

The worked example below adds `qdac.set_slew_rate`, which limits how fast a channel may change its output voltage.

**1. The node.** Attributes are plain and public, so the inherited `variables()`, `buses()`, equality, and hashing all work. `BUS_ATTRS` needs no declaration as long as the bus attribute is called `bus`. `expression_tokens` is imported inside the method to keep the module import graph flat.

```python
# operations.py
from qprogram.operations.operation import Operation
from qprogram.variable import Expression


class SetSlewRate(Operation):
    """A limit on how fast a QDAC channel may change its output voltage.

    Args:
        bus (str): QDAC channel whose slew rate is being limited.
        rate (float | Expression): Maximum rate of change in volts per second. Accepts a literal
            or any :class:`~qprogram.Expression`.
    """

    def __init__(self, bus: str, rate: float | Expression) -> None:
        self.bus = bus
        self.rate = rate

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qdac.set_slew_rate`` plus the tokens the ``rate`` argument contributes."""
        from qprogram.protocol import expression_tokens  # ruff: ignore[import-outside-top-level]

        return {"vendor.qdac.set_slew_rate"} | expression_tokens(self.rate)
```

Constructor arguments are documented on the class, `__init__` carries no docstring of its own, and a summary opening with "Return" stands in for a `Returns:` section. [Style notes](contributing.md#style-notes) has the rest.

**2. The namespace method.** This is the surface users see, so the signature and the docstring carry the types and the units.

```python
# namespace.py
def set_slew_rate(self, bus: str, rate: float | Expression) -> None:
    """Append a :class:`~qprogram_qdac.operations.SetSlewRate` operation.

    Args:
        bus (str): QDAC channel whose slew rate is being limited.
        rate (float | Expression): Maximum rate of change in volts per second. Accepts a
            literal ``float`` or any :class:`~qprogram.Expression`.
    """
    self._append(SetSlewRate(bus=bus, rate=rate))
```

**3 and 4. The token.** Register it, then put it in the profile's set.

```python
# profiles.py
register_capability_tokens(
    "vendor.qdac.wait_trigger",
    "vendor.qdac.set_trigger",
    "vendor.qdac.set_offset",
    "vendor.qdac.play",
    "vendor.qdac.set_slew_rate",
)

_BUS_OPS: frozenset[str] = frozenset(
    {
        "vendor.qdac.wait_trigger",
        "vendor.qdac.set_trigger",
        "vendor.qdac.set_offset",
        "vendor.qdac.play",
        "vendor.qdac.set_slew_rate",
    },
)
```

**5. The registration.** One line next to the others, plus the import and the `__all__` entry.

```python
# __init__.py
register_vendor_operation("qdac", "set_slew_rate", SetSlewRate)
```

Serialization comes for free. The default serializer reflects on `__init__` to emit positional arguments in order and keyword arguments only when they differ from their default, and the parser drives itself from the same signature:

<!-- check: skip -->
```
#!QProgram 0.2

require qdac 0.1

body:
  qdac.set_slew_rate "flux_q0" 0.05
```

Adding an operation is a minor version bump of the vendor protocol. Older files keep loading, because the parser accepts any `require` line the installed extension can satisfy, and an older file never mentions the operation that was added. Changing the wire form of one that already ships is the case that needs work, and [Changing one that already exists](#changing-one-that-already-exists) below walks through it.

### The tests that come with it

Each new operation earns one test per module in `tests/`:

- `test_operations.py`: construction, `buses()`, `variables()`, structural equality against an identical node, and `required_capabilities()` for both a literal and an `Expression` argument.
- `test_namespace.py`: the method appends the right node to the active block, and a bus from a foreign schema is rejected.
- `test_serialization.py`: a round trip through `dumps` and `loads`, that default-valued arguments are suppressed on the way out and restored on the way back, and that the `require qdac` line appears.
- `test_registration.py`: the class resolves in the registry under `("qdac", "set_slew_rate")`.
- `test_profile.py`: a program using the operation validates clean against the profile, and any predicate you added fires on the case it should and stays quiet otherwise.

[Contributing](contributing.md) has the rest of the checklist: the docs pages and the API reference entry that go in the same pull request.

### Changing one that already exists

Renaming an operation, renaming or reordering a constructor parameter, or giving an argument a new meaning breaks every file that already uses it. That is a major bump of the vendor protocol, and the release that does it registers a rewrite so that the files users already have go on loading.

Say 1.0 makes `dwell` required on `qdac.play`, where it had been optional with a default of `1`. A file written against 0.3 leaves it out, so the parser would hand `Play.__init__` one argument short:

<!-- check: skip -->
```
#!QProgram 0.2

require qdac 0.3

body:
  qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000)
```

The rewrite goes in `__init__.py` beside the `register_vendor_operation` calls, so that the import a `require qdac` line triggers is what registers it:

```python
# __init__.py
import re

from qprogram.serialization.migrations import register_vendor_migration

_PLAY = re.compile(r"^\s*qdac\.play\b.*$")


@register_vendor_migration("qdac", "1.0")
def _play_took_a_dwell(lines: list[str]) -> list[str]:
    """Give a pre-1.0 play line the dwell that release made required."""
    return [_PLAY.sub(r"\g<0> dwell=1", line) for line in lines]
```

The pattern matches the operation keyword and `\g<0>` appends to the whole line, rather than trying to pick the argument list apart: a waveform constructor carries commas and spaces of its own, and a swept argument carries parentheses. The value appended is the default that release removed, so a file that never said `dwell` keeps the behavior it had, and the parser binds the keyword by name like any other.

Four rules govern the rewrite:

- **The version is this package's, not the format's.** The chain is bounded by the installed extension, so `require qdac 0.3` read against an installed 1.0.1 runs every rewrite keyed above 0.3 and no higher than 1.0. A file already at 1.0 runs none of them.
- **One rewrite per breaking change, keyed to the release that ships it.** A release that only adds operations registers nothing. One keyed to a version that has not shipped yet never runs, so it can land in the same pull request as the change it repairs.
- **The pattern has to be narrow.** A migration is text in and text out with no parse in between, so anchor it on something only the syntax being changed produces. Here that is the `qdac.play` keyword at the head of a line.
- **Lines in, as many lines out.** The rewrite is handed every line of the file, header and `require` lines included, and the core refuses one that hands back a different number, since a diagnostic's line number has to go on pointing at the line the author wrote.

`tests/test_serialization.py` is where it earns its test, and that test is a load rather than a call to the function, since the registration and the version check are half of what is being proved:

```python
def test_a_0_3_file_gets_the_dwell_1_0_made_required():
    text = '#!QProgram 0.2\n\nrequire qdac 0.3\n\nbody:\n  qdac.play "flux_q0" "ramp_up"\n'
    assert qp.loads(text).body.elements[0].dwell == 1
```

A vendor rewrite only ever sees `.qp` lines. A `.wfl` waveform library carries no `require` line and so claims no vendor version, which leaves its own versioning to the core, whose [serialization internals](https://qilimanjaro-tech.github.io/qprogram/developer/serialization-internals.html#vendor-migrations) document the mechanism these calls reach into.
