# Saving and loading

QDAC operations cross the `.qp` boundary through the core serializer. Importing `qprogram_qdac` registers the four operations with it, so `qp.dumps` and `qp.loads` treat them the way they treat `play` or `measure`. This package carries no writer and no parser of its own.

```python
import qprogram as qp

from qprogram_qdac import QProgram

program = QProgram()
program.qdac.set_offset("flux_q0", 0.42)

text = qp.dumps(program)  # program -> str
program = qp.loads(text)  # str -> program

qp.save(program, "flux_bias.qp")  # program -> file
program = qp.load("flux_bias.qp")  # file -> program
```

The format itself, the grammar, and the rules that apply to every operation are documented in the [core `.qp` file format reference](https://qilimanjaro-tech.github.io/qprogram/reference/qp-format.html). This page covers the qdac-specific part.

## The `require` line

A file holding qdac operations names the vendor once, above the body:

```
#!QProgram 0.2

require qdac 0.2

body:
  qdac.set_offset "flux_q0" 0.42
```

The writer emits that line for any program that touches a qdac operation, wherever the operation sits. A `set_offset` reachable only through a conditional arm still gets the file declared:

```python
import qprogram as qp

from qprogram_qdac import QProgram

program = QProgram()
handle = program.measure("readout_q0", "readout", "weights", name="m0")
with program.if_(handle.state == 1):
    program.qdac.set_offset("flux_q0", 0.1)

print(qp.dumps(program))
```

```
#!QProgram 0.2

require qdac 0.2

body:
  measure "readout_q0" "readout" "weights" name="m0"
  if m0.state == 1:
    qdac.set_offset "flux_q0" 0.1
```

The parser does not require the converse. A hand-written file that calls `qdac.set_offset` with no `require` line loads fine as long as this package is already imported. Without the import there is nothing to activate, and the first dotted statement fails instead:

```
ParseError: Line 4: unknown vendor operation qdac.'set_offset': no operation is registered under that name. Import the 'qdac' extension package before loading, and check the file's `require qdac <x.y>` declaration.
```

## Where the version comes from

`qprogram_qdac/__init__.py` resolves its own installed version from `importlib.metadata` and hands it to the serialization registry:

```python
from importlib.metadata import PackageNotFoundError, version

from qprogram.serialization.registry import register_vendor_version

try:
    __version__ = version("qprogram-qdac")
except PackageNotFoundError:
    __version__ = "0.0.0"

register_vendor_version("qdac", __version__)
```

The `register_vendor_version` call is the whole version contract. The registry keeps the full string, `0.2.0` for this release, and the writer truncates it to `major.minor` on the `require` line, because compatibility is decided at that granularity and the patch component is informational.

Running from a source tree with no installed metadata leaves `__version__` at `0.0.0`, and every file requiring `qdac 0.1` then asks for more than is installed. Install the package, in editable mode if you are working on it, rather than putting `src/` on `PYTHONPATH`.

## Version mismatches

The parser resolves each `require` line against the registered version before it reads the body. One rule decides the outcome: the installed package must be able to provide what the line asks for. With `qdac 0.2.0` installed, `require qdac 0.2` and `require qdac 0.1` load, and these fail:

```
ParseError: Line 3: file requires qdac 1.0, newer than the installed qdac 0.2.0 — install qdac 1.0 or newer
ParseError: Line 3: file version '0.1.0' must be exactly major.minor
```

An older line is the readable case: `0.1` loads under an installed `0.3`, because a minor release only adds operations, and an older line whose spelling did change is repaired by the [migration](../developer/lowering.md#changing-one-that-already-exists) that release registered — so an earlier major loads too. A file that asks for a version this package does not have would reference statements it cannot build, so it is refused up front. The line carries `major.minor` and nothing else: a patch release of this package changes code and never the wire form, so there is no patch for a file to declare.

## Auto-activation

`pyproject.toml` declares a vendor-discovery entry point:

```toml
[project.entry-points."qprogram.vendors"]
qdac = "qprogram_qdac"
```

The name is the vendor namespace, the value is the module whose import side effects do the registration. When `loads` meets `require qdac` for a vendor that is not registered yet, it looks the name up in that entry-point group and imports the module on the spot. So a `.qp` file loads in any environment where this package is installed, imported or not:

```python
import sys

import qprogram as qp

TEXT = """#!QProgram 0.2

require qdac 0.2

body:
  qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=2000) dwell=200
"""

print("qprogram_qdac imported?", "qprogram_qdac" in sys.modules)
program = qp.loads(TEXT)
print("qprogram_qdac imported?", "qprogram_qdac" in sys.modules)
print(type(program.body.elements[0]).__module__)
```

```
qprogram_qdac imported? False
qprogram_qdac imported? True
qprogram_qdac.operations
```

Discovery only runs for vendors that are not registered yet, and only from a `require` line. Pass `auto_activate=False` to turn it off, and an unimported extension becomes a hard error:

```
ParseError: Line 3: file requires vendor 'qdac' 0.1 but no matching extension is registered in this environment — auto-activation is disabled; import the extension before loading (e.g. `import qprogram_qdac`)
```

Editing the entry point means re-installing the package: the group is read from the installed metadata, so `uv sync` has to run before the new line takes effect.

## Statement form

Every qdac operation is one line, dotted with the vendor name:

```
qdac.<operation> <positional arguments> [<keyword>=<value> ...]
```

Positional arguments come in constructor order, then optional keywords in any order. Arguments left at their default are not written out. The parser feeds the tokens back through `inspect.signature`, so the four operations need no per-class serialization code:

| Operation | Wire form |
|---|---|
| `wait_trigger` | `qdac.wait_trigger "flux_q0" 2` |
| `set_trigger` | `qdac.set_trigger "flux_q0" 100 position="end_step" outputs=[1, 3]` |
| `set_offset` | `qdac.set_offset "flux_q0" 0.42` |
| `play` | `qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=2000)` |

## How arguments are spelled

Quoting is the type distinction. A quoted token is a plain string: a raw bus name, a waveform alias, a `position` choice. A bare token is a variable reference or a schema-backed bus path.

| Value | Wire form | Where it appears |
|---|---|---|
| Raw bus name | `"flux_q0"` | the first argument of every operation |
| Schema-backed bus | `q[0].flux` | the first argument of every operation |
| Number | `2`, `100`, `0.42` | `port`, `duration`, `offset`, `dwell`, `delay`, `repetitions` |
| Boolean | `true`, `false` | `stepped` |
| String choice | `"end_step"` | `position` |
| Waveform alias | `"flux_pulse"` | `play`'s waveform |
| Inline waveform | `Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=2000)` | `play`'s waveform |
| Variable reference | `bias` | `offset` |
| Expression | `((bias * 0.5) - 0.25)` | `offset` |
| Sequence | `[1, 3]` | `outputs` |

Two generic writer forms have no qdac argument to land on: brace-dict literals (`matrix={"a": 1.0}`) for mapping arguments, and `null` for `None`. No qdac operation takes a mapping, and none of their optional arguments defaults to `None`.

Expressions are always parenthesized, and they are argument values rather than sub-expressions: `set_offset` takes one, a waveform constructor argument does not. `Ramp(from_amplitude=(bias * 0.5), ...)` is a parse error even though the builder accepts it and the writer emits it.

Every shape in one program:

```python
import qprogram as qp
from qprogram.waveforms import Ramp, Square

from qprogram_qdac import QProgram

program = QProgram()
bias = program.variable("bias")
with program.sweep(bias, qp.Range(start=0.0, stop=1.0, step=0.1)):
    program.qdac.set_offset("flux_q0", 0.42)
    program.qdac.set_offset("flux_q0", bias)
    program.qdac.set_offset("flux_q0", (bias * 0.5) - 0.25)
    program.qdac.set_trigger("flux_q0", 100, outputs=[1])
    program.qdac.set_trigger("flux_q0", 100, position="end_step", outputs=(3, 1, 3))
    program.qdac.wait_trigger("flux_q0", 2)
    program.qdac.play("flux_q0", "flux_pulse")
    program.qdac.play("flux_q0", Ramp(0.0, 1.0, 2000))
    program.qdac.play("flux_q0", Square(0.3, 1000), dwell=200, delay=50, repetitions=2, stepped=True)

print(qp.dumps(program))
```

```
#!QProgram 0.2

require qdac 0.2

body:
  var bias

  for bias in Range(start=0.0, stop=1.0, step=0.1):
    qdac.set_offset "flux_q0" 0.42
    qdac.set_offset "flux_q0" bias
    qdac.set_offset "flux_q0" ((bias * 0.5) - 0.25)
    qdac.set_trigger "flux_q0" 100 outputs=[1]
    qdac.set_trigger "flux_q0" 100 position="end_step" outputs=[1, 3]
    qdac.wait_trigger "flux_q0" 2
    qdac.play "flux_q0" "flux_pulse"
    qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=2000)
    qdac.play "flux_q0" Square(amplitude=0.3, duration=1000) dwell=200 delay=50 repetitions=2 stepped=true
```

### Buses

Every qdac operation takes its channel in the `bus` argument, and the parser treats that argument as a bus reference, so a schema-backed value writes as a bare path and comes back a `BusRef`. A quoted string stays a string even when it looks like a path:

```python
import qprogram as qp
from qprogram.buses import BusRef, FluxTunableTransmonSchema

from qprogram_qdac import QProgram

schema = FluxTunableTransmonSchema()
program = QProgram(schema=schema)
program.qdac.set_offset(schema.q[0].flux, 0.1)
program.qdac.set_offset("q[0].flux", 0.2)

for op in qp.loads(qp.dumps(program)).body.elements:
    print(isinstance(op.bus, BusRef), str(op.bus))
```

```
True q0/flux
False q[0].flux
```

Two things have to line up for a promotion: the operation must list the argument as bus-carrying, which all four do for `bus`, and the token must have arrived bare. The second half is what keeps a raw bus name shaped like a path out of the schema, and what lets the quoted value round-trip unchanged.

### Outputs

`outputs` accepts any iterable of integers. Whatever the caller passes, `SetTrigger` stores a sorted tuple of unique indices, and that is what the bracket literal holds. A hand-written comma-separated string is accepted too, and normalizes the same way:

```python
import qprogram as qp
import qprogram_qdac  # registers the qdac operations with the serializer

TEXT = """#!QProgram 0.2

require qdac 0.2

body:
  qdac.set_trigger "flux_q0" 100 outputs="2,1,2"
"""

program = qp.loads(TEXT)
print(program.body.elements[0].outputs)
print(qp.dumps(program).splitlines()[-1])
```

```
(1, 2)
  qdac.set_trigger "flux_q0" 100 outputs=[1, 2]
```

## A full round trip

A flux-bias sweep, with a schema, metadata, a variable, a swept offset, and all four operations:

```python
import qprogram as qp
from qprogram.buses import FluxTunableTransmonSchema
from qprogram.waveforms import Ramp

from qprogram_qdac import QProgram

schema = FluxTunableTransmonSchema()
program = QProgram(schema=schema, label="flux-bias-sweep", description="QDAC flux bias sweep")
bias = program.variable("bias", label="Flux bias", units="V")
flux = schema.q[0].flux

with program.sweep(bias, qp.Linspace(start=-0.5, stop=0.5, num=11)):
    program.qdac.set_offset(flux, bias)
    program.qdac.set_trigger(flux, 100, position="step", outputs={2, 1})
    program.qdac.play(flux, Ramp(0.0, 1.0, 2000), dwell=200, repetitions=4)
    program.qdac.wait_trigger(flux, port=3)

text = qp.dumps(program)
print(text)

reloaded = qp.loads(text)
print("text equal:", qp.dumps(reloaded) == text)
print("body equal:", reloaded.body == program.body)
```

```
#!QProgram 0.2

require qdac 0.2

metadata:
  label: "flux-bias-sweep"
  description: "QDAC flux bias sweep"

schema:
  element q:
    drive info=IQ
    readout info=IQ+acquires
    flux info=single

body:
  var bias label="Flux bias" units="V"

  for bias in Linspace(start=-0.5, stop=0.5, num=11):
    qdac.set_offset q[0].flux bias
    qdac.set_trigger q[0].flux 100 position="step" outputs=[1, 2]
    qdac.play q[0].flux Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=2000) dwell=200 repetitions=4
    qdac.wait_trigger q[0].flux 3
```

```
text equal: True
body equal: True
```

Both halves of the guarantee hold: the reloaded program is structurally equal to the original, and serializing the copy reproduces the same text byte for byte.

## Where the parser stays strict

A qdac statement fails to load rather than losing content. Each of these three bodies puts its one statement on line 6:

```python
import qprogram as qp
import qprogram_qdac  # registers the qdac operations with the serializer

HEAD = """#!QProgram 0.2

require qdac 0.2

body:
"""

for statement in (
    'qdac.set_offset "flux_q0" 0.1 0.2',
    'qdac.play "flux_q0" "flux_pulse" dwel=200',
    'qdac.frobnicate "flux_q0"',
):
    try:
        qp.loads(HEAD + "  " + statement + "\n")
    except qp.ParseError as error:
        print(f"ParseError: {error}")
```

```
ParseError: Line 6: too many arguments for 'SetOffset': 3 positional tokens but the operation takes at most 2; unexpected: ['0.2']. If you meant an arithmetic expression, parenthesize it: `(100 - t)`.
ParseError: Line 6: cannot construct 'Play' from the given arguments: Play.__init__() got an unexpected keyword argument 'dwel'. Did you mean 'dwell'?
ParseError: Line 6: unknown vendor operation qdac.'frobnicate': no operation is registered under that name. Import the 'qdac' extension package before loading, and check the file's `require qdac <x.y>` declaration.
```

Loading is a syntax and signature check, not a capability check. A file whose `set_trigger` arms no outputs parses, and the `qdac.empty-trigger-outputs` diagnostic comes from `qp.validate` afterwards.

## See also

- [Operations](operations.md) covers the builder side of each statement: the arguments, their defaults, and which of them accept an expression.
- [Capabilities and profiles](capabilities.md) covers what validation adds on top of a successful load.
- The core project's [.qp file format reference](https://qilimanjaro-tech.github.io/qprogram/reference/qp-format.html) specifies the grammar these statements sit inside: the header, the `schema:` block, and the value literals.
