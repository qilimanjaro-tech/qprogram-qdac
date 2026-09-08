# QProgram QDAC

[![Tests](https://github.com/qilimanjaro-tech/qprogram-qdac/actions/workflows/tests.yml/badge.svg)](https://github.com/qilimanjaro-tech/qprogram-qdac/actions/workflows/tests.yml) [![Code Quality](https://github.com/qilimanjaro-tech/qprogram-qdac/actions/workflows/code_quality.yml/badge.svg)](https://github.com/qilimanjaro-tech/qprogram-qdac/actions/workflows/code_quality.yml) [![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/) [![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

QDevil QDAC extensions for [QProgram](https://github.com/qilimanjaro-tech/qprogram), the pulse-level quantum programming DSL. The QDAC is a slow high-precision DAC, used most often for flux biasing.

The core DSL knows nothing about any instrument. This package adds the `qdac` vendor namespace to it: four operations covering DC offsets, the waveform engine, and the chassis trigger network, a capability profile that says what a QDAC channel can do, and `.qp` serialization for all of it. Importing the package is what turns those on.

## Installation

```bash
pip install qprogram-qdac
```

The only dependency is `qprogram` itself.

## A first program

```python
import qprogram as qp
from qprogram import BusSchema
from qprogram.waveforms import IQPair, Square
from qprogram_qdac import QProgram

schema = BusSchema.flux_tunable_transmon()
q = schema.q

program = QProgram(label="flux-spectroscopy", schema=schema)
bias = program.variable("bias", units="V")

with program.sweep(bias).from_range(-0.2, 0.2, 0.01):
    program.qdac.set_offset(q[0].flux, bias)
    with program.average(shots=100):
        program.play(q[0].drive, "pi_pulse")
        program.sync([q[0].drive, q[0].readout])
        m0 = program.measure(q[0].readout, "readout", "weights")

resolved = program.with_waveforms(
    {
        "pi_pulse": IQPair(Square(0.5, 40), Square(0.0, 40)),
        "readout": IQPair(Square(1.0, 2000), Square(0.0, 2000)),
        "weights": IQPair(Square(1.0, 2000), Square(1.0, 2000)),
    }
)

result = qp.simulate(resolved)
data = result.get(m0)
print(data.dims, data.shape)  # ('bias', 'IQ') (41, 2)
```

The flux bias comes from the QDAC, the drive and readout from whatever vendor owns those buses. One program describes both, and the nesting is what makes a mixed platform accept it: the bias sweep dispatches from the host, one upload per point, while the `average` block under it runs in the real-time sequencer. Flatten the two into one block and no domain runs both. `sync` names its buses because the argument-less form syncs every bus in the program, and a QDAC channel is not something a real-time barrier can wait on.

## What you get

- **Four operations under one namespace.** `set_offset` holds a DC voltage on a channel, `play` uploads an envelope to the channel's waveform engine with explicit dwell, delay, repetitions and stepped mode, and `set_trigger` / `wait_trigger` wire the channel into the chassis trigger network so QDAC sequences line up with instruments driving other buses.
- **Host-side sweeps, declared rather than guessed.** The QDAC has no FPGA, so a swept parameter has to be re-uploaded from the host between iterations. The `qdac-default-v1` profile says so through a domain constraint, and `qp.explain(program, capabilities)` prints the enclosing loop as `[host]` instead of failing at compile time.
- **Single-channel by declaration.** The profile lists only single-channel waveform tokens. An IQ waveform on a QDAC bus is a `missing-capability` error from `qp.validate`, not a runtime surprise.
- **Serialization included.** Every operation round-trips through the `.qp` text format, under a `require qdac 0.1` header line. A file that names `qdac` activates this package on load through its entry point, so the reader does not have to import it first.
- **Typed access.** `QProgram` from this package is the core builder with a typed `.qdac` property. `QdacMixin` composes with other vendor mixins when a platform spans several instruments.

## Documentation

Full documentation, including the operation reference, the capability profile, and the generated API reference, lives at <https://qilimanjaro-tech.github.io/qprogram-qdac/>.

## Development

The project uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/qilimanjaro-tech/qprogram-qdac
cd qprogram-qdac

uv sync --group dev                  # create .venv and install everything
uv run pytest                        # run the test suite
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run ty check                      # type-check
uv run --group docs zensical serve   # preview the documentation
```

## License

Apache License 2.0 - see [LICENSE](LICENSE).
