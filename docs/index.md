# QProgram QDAC

`qprogram-qdac` adds QDevil QDAC support to
[QProgram](https://qilimanjaro-tech.github.io/qprogram/), the pulse-level
quantum programming DSL. The QDAC is a slow high-precision DAC, used most
often for flux biasing.

The core DSL knows nothing about any instrument. This package plugs into it
through the vendor hooks and contributes three things: a `qdac` namespace
on every program, a capability profile describing what a QDAC channel can
do, and `.qp` serialization for the operations it adds. Importing the
package is what turns those on.

## What the qdac namespace gives you

| Operation                     | What it does                                                                                   |
|-------------------------------|------------------------------------------------------------------------------------------------|
| `program.qdac.set_offset`     | Hold a DC voltage on a channel until something changes it. The value may be a swept variable.  |
| `program.qdac.play`           | Upload an envelope to the channel's waveform engine, with dwell, delay, repetitions, stepped.   |
| `program.qdac.set_trigger`    | Arm chassis trigger outputs to fire at a sequence position, for a given duration.               |
| `program.qdac.wait_trigger`   | Halt the channel's sequencer until an external trigger arrives on an input port.                |

Two facts about the instrument are declared in the profile rather than
left in a comment. The QDAC has **no FPGA**, so a swept parameter is
re-uploaded from the host between iterations, and `qdac-default-v1` puts
the enclosing loop host-side. A QDAC channel is **single-channel**, so the
profile carries no IQ waveform tokens at all: an IQ pulse on a QDAC bus is
a `missing-capability` error from `qp.validate`.

## A first program

```python
import qprogram as qp
from qprogram import BusSchema
from qprogram.waveforms import Ramp
from qprogram_qdac import QProgram

schema = BusSchema.flux_tunable_transmon()
flux = schema.q[0].flux

program = QProgram(label="flux-ramp", schema=schema)
program.qdac.set_offset(flux, 0.42)
program.qdac.set_trigger(flux, duration=50, position="start", outputs={1, 2})
program.qdac.play(flux, Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000), dwell=100)
program.qdac.wait_trigger(flux, port=3)

print(qp.dumps(program))
```

That prints the program as `.qp` text:

```
#!QProgram 1.0

require qdac 0.1

metadata:
  label: "flux-ramp"

schema:
  element q:
    drive info=IQ
    readout info=IQ+acquires
    flux info=single

body:
  qdac.set_offset q[0].flux 0.42
  qdac.set_trigger q[0].flux 50 outputs=[1, 2]
  qdac.play q[0].flux Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000) dwell=100
  qdac.wait_trigger q[0].flux 3
```

The `require qdac 0.1` line is the whole compatibility story. `qp.load`
checks it against the installed extension, and imports this package on
demand if the reader never did.

## Where to go next

| If you want to ...                                   | Read                                                        |
|------------------------------------------------------|-------------------------------------------------------------|
| install the package and run something                | [Getting started](getting-started.md)                       |
| see every operation and its arguments                | [Operations](guide/operations.md)                           |
| know which programs a QDAC platform will accept      | [Capabilities and profiles](guide/capabilities.md)          |
| read the `.qp` wire form of each operation           | [Saving and loading](guide/serialization.md)                |
| browse the generated API                             | [API reference](reference/api.md)                           |
| map the operations onto QDAC hardware                | [Lowering onto hardware](developer/lowering.md)             |
| work on this package                                 | [Contributing](developer/contributing.md)                   |

## Status

The vendor protocol version is this package's own version, and `.qp` files
carry it as `require qdac <major>.<minor>`. A file loads against any
installed `qprogram-qdac` that shares its major version and is no older in
minor. Anything else is a `ParseError` rather than a partial load. The
Python API is pre-1.0 and allowed to move; the wire form is the steadier
of the two.
