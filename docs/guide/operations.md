# Operations

This package ships four operations, all of them behind the `qdac` vendor
namespace. The call shape is always

```text
program.qdac.<operation>(...)
```

| Operation      | What it programs on the instrument                          |
|----------------|-------------------------------------------------------------|
| `set_offset`   | The channel's DC source: hold one constant voltage.          |
| `set_trigger`  | The chassis trigger bus: arm outputs to fire at a sequence event. |
| `wait_trigger` | The channel's sequence: halt until an external trigger arrives. |
| `play`         | The channel's waveform engine: emit an envelope.              |

The conventions:

- The first argument of every operation is `bus`, a QDAC channel. A plain
  string or a `BusRef` both work. A `BusRef` that came from a different
  `BusSchema` than the program's is rejected; nothing else about the bus is
  checked at build time.
- Because all four operations carry a `bus`, all four route to that bus's
  capability slot. QDAC has no FPGA, so a platform normally fills the `host`
  half of that slot and leaves `rt` empty. Every qdac operation is then
  dispatched from the host over the chassis slow-control link rather than
  compiled into a real-time sequencer program. See
  [Capabilities and profiles](capabilities.md).
- Only two things in this package accept an `Expression` and can be swept:
  `set_offset`'s `offset`, and the parameters of the waveform handed to `play`.
  Everything else is typed `int`, `bool`, or a string literal and is fixed when
  the program is built.

## Getting the namespace

Importing the package is the activation step. It registers the namespace on the
base `QProgram`, so the dynamic form works everywhere:

```python
import qprogram as qp
import qprogram_qdac  # the import registers the qdac namespace

program = qp.QProgram()
program.qdac.set_offset("flux_q0", 0.42)
```

For autocomplete, use the pre-combined class from this package instead. It is
`qprogram.QProgram` with `.qdac` spelled out as a typed property:

```python
from qprogram_qdac import QProgram

program = QProgram(label="flux-bias")
program.qdac.set_offset("flux_q0", 0.42)
```

The examples below use a flux-tunable transmon schema so the buses are typed:

```python
from qprogram.buses import BusSchema
from qprogram.waveforms import Ramp, Square

schema = BusSchema.flux_tunable_transmon()
q = schema.q

q[0].flux  # 'q0/flux', a single-channel BusRef
```

## `set_offset(bus, offset)`

Hold a QDAC channel at a constant voltage. The channel keeps that voltage until
another operation changes it, so this is the operation that sets a flux bias
point and leaves it there.

| Argument | Type                  | Meaning                                        |
|----------|-----------------------|------------------------------------------------|
| `bus`    | `str` / `BusRef`      | QDAC channel whose DC offset is set.            |
| `offset` | `float` / `Expression`| Target offset in volts.                         |

```python
program = QProgram(label="bias-point", schema=schema)
program.qdac.set_offset(q[0].flux, 0.42)
program.qdac.set_offset(q[1].flux, -0.05)
```

`offset` is the one qdac argument that takes an `Expression`, so it is the one
you sweep directly. A `Variable` works, and so does any expression built from
one:

```python
program = QProgram(label="flux-arc", schema=schema)
bias = program.variable("bias", units="V")
with program.sweep(bias, qp.Range(-0.2, 0.3, 0.1)):
    program.qdac.set_offset(q[0].flux, bias)
    program.qdac.set_offset(q[1].flux, bias * 0.5)
```

On the instrument side this lowers to one slow-control write per value: the
platform pushes `offset` to the channel's DC source over the chassis link. A
swept `offset` is re-uploaded once per iteration, which is why the loop that
binds the variable dispatches host-side rather than as a hardware loop.

Capability tokens: `vendor.qdac.set_offset`, plus one `expr.*` token per node
kind in the offset expression (`expr.variable`, `expr.binary_op`,
`expr.constant`, and so on). The `expr.*` tokens are always checked against the
platform slot, never against the bus slot.

## `set_trigger(bus, duration, position="start", outputs=())`

Arm one or more of the chassis trigger outputs to fire at a chosen point in the
channel's sequence. This is how a QDAC sequence hands timing to another
instrument.

| Argument   | Type                 | Meaning                                             |
|------------|----------------------|-----------------------------------------------------|
| `bus`      | `str` / `BusRef`     | QDAC channel whose trigger outputs are configured.   |
| `duration` | `int`                | Trigger-active duration in nanoseconds.              |
| `position` | `str` literal        | Sequence event at which the triggers fire.           |
| `outputs`  | iterable of `int`    | Trigger output indices to arm. Empty by default.     |

`position` takes one of four values:

| `position`   | Fires                                                  |
|--------------|--------------------------------------------------------|
| `"start"`    | When the sequence begins. The default.                  |
| `"step"`     | At the start of every step of a stepped sequence.       |
| `"end"`      | When the sequence finishes.                             |
| `"end_step"` | At the end of every step.                               |

```python
program = QProgram(label="trigger-out", schema=schema)
program.qdac.set_trigger(q[0].flux, 50, position="start", outputs={1, 2})
program.qdac.set_trigger(q[0].flux, 20, position="end_step", outputs=[4])
```

`outputs` accepts any iterable of integers. It is stored sorted with duplicates
dropped, so two spellings of the same output set build the same node, hash the
same, and serialize to the same `.qp` line:

```python
program = QProgram()
program.qdac.set_trigger("flux_q0", 50, position="step", outputs={3, 1, 1, 2})

program.body.elements[0].outputs  # (1, 2, 3)
```

An empty `outputs` arms a trigger that fires onto nothing. The profile treats
that as an error: see
[an empty trigger-output set is an error](capabilities.md#an-empty-trigger-output-set-is-an-error).

On the instrument side this lowers to trigger-network configuration: the
platform binds the named output lines to the sequence event and sets their pulse
width. Nothing is emitted on the DAC output.

Capability token: `vendor.qdac.set_trigger`.

## `wait_trigger(bus, port)`

Halt the channel's sequence until an external trigger arrives on a trigger
input port. Nothing is emitted while waiting. Pair it with `set_trigger` on
another instrument to start a QDAC sequence from a fast sequencer's clock.

| Argument | Type             | Meaning                                                    |
|----------|------------------|------------------------------------------------------------|
| `bus`    | `str` / `BusRef` | QDAC channel whose trigger input the sequence listens on.   |
| `port`   | `int`            | Trigger input port on the chassis. Chassis-defined, typically 1-based. |

```python
program = QProgram(label="trigger-in", schema=schema)
program.qdac.wait_trigger(q[0].flux, port=3)
program.qdac.play(q[0].flux, Ramp(0.0, 1.0, 1000), dwell=100)
```

On the instrument side this lowers to a blocking wait in the channel's sequence,
armed on the given input line.

Capability token: `vendor.qdac.wait_trigger`.

## `play(bus, waveform, dwell=1, delay=0, repetitions=1, stepped=False)`

Upload an envelope to the channel's waveform engine and emit it. This is the one
operation here that produces a shaped output rather than a static level.

| Argument      | Type             | Meaning                                                        |
|---------------|------------------|----------------------------------------------------------------|
| `bus`         | `str` / `BusRef` | QDAC channel that emits the waveform.                           |
| `waveform`    | `Waveform`       | Single-channel envelope to emit.                                |
| `dwell`       | `int`            | Per-sample dwell time in nanoseconds. Sets the emission rate.   |
| `delay`       | `int`            | Delay in nanoseconds between sequence start and the first sample. |
| `repetitions` | `int`            | How many times the engine repeats the envelope. `1` plays it once. |
| `stepped`     | `bool`           | `True` steps through samples discretely, `False` interpolates continuously. |

```python
program = QProgram(label="flux-ramp", schema=schema)
program.qdac.play(q[0].flux, Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000), dwell=100)
program.qdac.play(q[0].flux, Square(0.35, 2000), dwell=200, delay=500, repetitions=4, stepped=True)
```

QDAC is single-channel. `play` always claims `waveform.single`, and the profile
lists single-channel waveform classes only, so an IQ envelope on a qdac bus
fails validation with a `missing-capability` diagnostic. The
[capabilities page](capabilities.md#capability-tokens) has the token list and
the exact message.

Waveform parameters accept `Expression`s, so a swept envelope parameter works
through `play`:

```python
program = QProgram(label="ramp-sweep", schema=schema)
top = program.variable("top")
with program.sweep(top, qp.Range(0.1, 0.5, 0.1)):
    program.qdac.play(q[0].flux, Ramp(0.0, top, 1000), dwell=100)
```

A string alias is accepted in the waveform position, the same as anywhere else
in QProgram. The profile names concrete waveform classes, so resolve aliases
before handing the program to a platform:

```python
program = QProgram(label="aliased", schema=schema)
program.qdac.play(q[0].flux, "flux_ramp")

program = program.with_waveforms({"flux_ramp": Ramp(0.0, 1.0, 1000)})
```

On the instrument side this lowers to a waveform-engine program: the envelope's
samples, plus `dwell`, `delay`, `repetitions`, and the stepped-or-continuous
mode. The profile records the engine's dwell floor as the `min_dwell_ns` limit.

Capability tokens: `vendor.qdac.play`, `waveform.single`, and the per-class
token of the envelope (`waveform.ramp`, `waveform.square`, and so on).

## What can be swept

| Operation      | Arguments accepting an `Expression`       |
|----------------|-------------------------------------------|
| `set_offset`   | `offset`                                   |
| `play`         | any parameter of the `waveform`            |
| `set_trigger`  | none                                       |
| `wait_trigger` | none                                       |

`duration`, `port`, `dwell`, `delay`, and `repetitions` are typed `int`,
`stepped` is typed `bool`, and `position` is one of four string literals. They
are values you choose when building the program.

Whenever a qdac operation does reference a loop-bound variable, whether through
`offset` or through a waveform parameter, the loop that binds that variable
dispatches host-side. The rule and the diagnostic it produces are in
[Capabilities and profiles](capabilities.md#swept-variables-force-the-loop-host-side).

## Running one end to end

Core qprogram's reference executor runs qdac programs without an instrument
attached. Vendor operations execute generically there: measurements record
results, other operations evaluate their expressions and are otherwise no-ops.
That is enough to check that a flux sweep produces the array shape you expect:

```python
import numpy as np
from qprogram import MockMeasurementModel
from qprogram.waveforms import IQPair

model = MockMeasurementModel(response=lambda bus, env: (0.5 - abs(env["bias"])) + 0j, seed=3)

program = QProgram(label="flux-arc")
bias = program.variable("bias", units="V")
with program.sweep(bias, qp.Range(-0.2, 0.3, 0.1)):
    program.qdac.set_offset("flux_q0", bias)
    with program.average(100):
        program.measure("readout_q0", IQPair(Square(1.0, 2000), Square(0.0, 2000)), "weights")

result = qp.simulate(program, model=model)
da = result.get("m0")

da.dims  # ('bias', 'IQ')
np.round(da.sel(IQ="I").values, 3)  # array([0.3, 0.4, 0.5, 0.4, 0.3, 0.2])
```

## What an operation looks like in the AST

Every operation is a typed class with explicit attributes. `vars(op)` is the
constructor view:

```python
program = QProgram(label="ast", schema=schema)
program.qdac.play(q[0].flux, Ramp(0.0, 1.0, 1000), dwell=100)
op = program.body.elements[0]

type(op).__name__  # 'Play'
op.bus  # 'q0/flux'
op.dwell  # 100
op.stepped  # False
sorted(op.required_capabilities())
# ['vendor.qdac.play', 'waveform.ramp', 'waveform.single']
```

The classes live in `qprogram_qdac.operations` (`SetOffset`, `SetTrigger`,
`WaitTrigger`, `Play`) and are exported from the package root. You rarely
construct them by hand, but transformations and tests do.

## Wire form

Each operation serializes as `qdac.<name>` plus its arguments. Arguments equal
to their default are omitted:

```text
qdac.set_offset "flux_q0" 0.42
qdac.set_trigger "flux_q0" 50 position="end_step" outputs=[1, 3]
qdac.wait_trigger "flux_q0" 3
qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000) dwell=100
```

A file carrying any of those lines declares `require qdac 0.1` in its header.
[Saving and loading](serialization.md) covers the header, the version rule, and
how a `.qp` file activates this package on load.

## See also

- [Capabilities and profiles](capabilities.md) covers `qdac-default-v1`, its
  tokens, limits, and the two predicates that reject or reclassify programs.
- [Lowering onto hardware](../developer/lowering.md) covers what a platform
  compiler does with these nodes.
- [API reference](../reference/api.md) has the generated signatures.
