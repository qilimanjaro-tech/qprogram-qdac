# Getting started

This page takes you from an empty environment to a QDAC program you can
run. It assumes Python 3.11 or newer and some familiarity with the
[core DSL](https://qilimanjaro-tech.github.io/qprogram/).

## Install

```bash
pip install qprogram-qdac
```

That pulls in `qprogram`, the only dependency. There are no extras.

### Working on this package

The repository uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/qilimanjaro-tech/qprogram-qdac
cd qprogram-qdac

uv sync --group dev
uv run pytest
```

To preview the documentation:

```bash
uv run --group docs zensical serve
```

## Importing is the activation step

Vendor registration happens as an import side effect. Importing
`qprogram_qdac` registers the `qdac` namespace on
[`QProgram`](https://qilimanjaro-tech.github.io/qprogram/), registers the
four operations with the `.qp` serializer, and registers the
`qdac-default-v1` capability profile. Nothing else is needed.

```python
import qprogram as qp
import qprogram_qdac  # importing is what registers the qdac vendor

program = qp.QProgram()
program.qdac.set_offset("flux_q0", 0.42)

print(qp.dumps(program))
```

The namespace attaches to the base class, so `.qdac` works on any program,
including one that was built before the import ran. In an interpreter that
never imports the package the attribute does not exist:

```python
import qprogram as qp

try:
    qp.QProgram().qdac
except AttributeError as error:
    print(f"AttributeError: {error}")
```

```text
AttributeError: No vendor namespace 'qdac' registered on QProgram
```

One case does not need the import at all. A `.qp` file whose header carries
`require qdac 0.1` makes the parser look up this package through its
`qprogram.vendors` entry point and import it on demand, so the file loads
even when the reader never mentioned QDAC:

```python
import qprogram as qp

text = """#!QProgram 1.0
require qdac 0.1
body:
  qdac.set_offset "flux_q0" 0.42
  qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000) dwell=100
"""

program = qp.loads(text)  # imports qprogram_qdac on the way
```

## The typed QProgram

`qprogram_qdac.QProgram` is the core builder with a typed `.qdac` property
already mixed in. Prefer it in scripts: the runtime behavior is identical,
but editors and type-checkers can see the operations and their signatures.

```python
from qprogram_qdac import QProgram

program = QProgram(label="flux-bias")
program.qdac.set_offset("flux_q0", 0.42)  # autocompleted and type-checked
```

## One program, several vendors

A platform usually spans several instruments: the QDAC biases the flux
buses while another vendor drives and reads out. Each vendor ships a mixin,
and the mixins compose by listing them ahead of the base class.

```python
import qprogram as qp
from qprogram import QProgram as BaseQProgram
from qprogram_qblox import QbloxMixin
from qprogram_qdac import QdacMixin


class QProgram(QbloxMixin, QdacMixin, BaseQProgram):
    """A program for a platform with both a QDAC and a Qblox cluster."""


program = QProgram(label="flux-bias-and-readout")
program.qdac.set_offset("flux_q0", 0.42)
program.qblox.acquire("readout_q0", "weights")

print(qp.dumps(program))
```

This one needs `qprogram-qblox` installed as well. The resulting file
carries a `require` line per vendor, and the parser checks each one against
the installed extension:

```
#!QProgram 1.0

require qblox 0.1
require qdac 0.1

metadata:
  label: "flux-bias-and-readout"

body:
  qdac.set_offset "flux_q0" 0.42
  qblox.acquire "readout_q0" "weights" name="m0"
```

## A first experiment

Save this as `flux_bias_sweep.py` and run it with
`python flux_bias_sweep.py`. It sweeps a flux bias on a QDAC channel, plays
a slow ramp from the waveform engine, measures the resonator at each bias
point, round-trips the program through the `.qp` text format, and runs it
against the reference software executor that ships with the core package.

```python
import qprogram as qp
from qprogram import BusSchema
from qprogram.waveforms import IQPair, Ramp, Square
from qprogram_qdac import QProgram

schema = BusSchema.flux_tunable_transmon()
q = schema.q

program = QProgram(label="flux-bias-sweep", schema=schema)
bias = program.variable("bias", units="V")

with program.sweep(bias).from_range(-0.2, 0.2, 0.02):
    program.qdac.set_offset(q[0].flux, bias)
    program.qdac.play(
        q[0].flux,
        Ramp(from_amplitude=0.0, to_amplitude=0.1, duration=1000),
        dwell=100,
    )
    with program.average(shots=100):
        m0 = program.measure(q[0].readout, "readout", "weights")

text = qp.dumps(program)
assert qp.dumps(qp.loads(text)) == text

resolved = program.with_waveforms(
    {
        "readout": IQPair(Square(1.0, 2000), Square(0.0, 2000)),
        "weights": IQPair(Square(1.0, 2000), Square(1.0, 2000)),
    }
)

result = qp.simulate(resolved)
data = result.get(m0)
print(data.dims, data.shape)  # ('bias', 'IQ') (21, 2)
```

Two things are worth noticing. The QDAC operations and the measurement live
in one program but not in one block: the sweep carries the slow bias and the
ramp, and the `average` under it carries the readout. A block whose
operation-children split between host-side and real-time has no domain that
runs both, so that nesting is what makes a mixed platform accept the
program. [Capabilities and profiles](guide/capabilities.md) builds such a
platform and validates this shape against it. And the waveform the QDAC
plays is a `Ramp` object bound at build time, while the readout pulse is
still the string `"readout"` until `with_waveforms` resolves it: the QDAC
waveform engine takes an envelope, not a calibrated pulse name.

`qp.dumps` and `qp.loads` have file counterparts in `qp.save` and
`qp.load`, which write and read the same text;
[Saving and loading](guide/serialization.md) covers the wire form.

`qp.simulate` is the core package's reference executor. It knows nothing
about QDAC hardware and runs vendor operations generically, which makes it
useful for checking program structure and result shapes before a real
platform is in reach. A QDAC platform implements the same
`PlatformProtocol` interface, and `platform.execute(resolved)` returns the
same result shape.

## Where to next?

- [Operations](guide/operations.md) documents each of the four operations,
  its arguments, and what the hardware does with them.
- [Capabilities and profiles](guide/capabilities.md) covers
  `qdac-default-v1`, the host-side dispatch rule, and reading the
  diagnostics.
- [Saving and loading](guide/serialization.md) shows the `.qp` wire form of
  every operation and the version-compatibility rules.
- [Lowering onto hardware](developer/lowering.md) is for anyone writing the
  platform that actually drives a QDAC.
