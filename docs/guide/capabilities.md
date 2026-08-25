# Capabilities and profiles

A platform declares what it supports as a `PlatformCapabilities` descriptor, and
`qp.validate` checks a program against that declaration before anything reaches
an instrument. This package ships one bundle for that declaration:
`qdac-default-v1`, the bus-level profile for a QDAC-driven channel.

If the protocol itself is new to you, read the core guide's
[capabilities page](https://qilimanjaro-tech.github.io/qprogram/guide/capabilities.html)
first. This page covers what `qdac-default-v1` puts in it.

## What the profile carries

Importing the package registers the profile, so it resolves by name:

```python
import qprogram as qp
from qprogram_qdac.profiles import QDAC_DEFAULT_V1

QDAC_DEFAULT_V1.name  # 'qdac-default-v1'
QDAC_DEFAULT_V1.version  # (0, 1, 0)
QDAC_DEFAULT_V1.extends  # None
QDAC_DEFAULT_V1.limits  # {'min_dwell_ns': 100}
QDAC_DEFAULT_V1.vendor_versions  # {'qdac': (0, 1, 0)}
len(QDAC_DEFAULT_V1.capabilities)  # 16
```

`extends` is `None`: the profile declares its own token set rather than
inheriting one. `vendor_versions` records which qdac extension version the
profile was written against, mirroring a `.qp` file's `require qdac 0.1` line.

Materialize it into a descriptor the same way as any other profile:

```python
qdac_cc = qp.CompilerCapabilities.from_profile("qdac-default-v1")

qdac_cc.profile  # 'qdac-default-v1'
qdac_cc.supports("vendor.qdac.set_offset")  # True
qdac_cc.supports("waveform.iq")  # False
```

## Capability tokens

Sixteen tokens, in two groups.

Four vendor operation tokens, one per operation this package ships. Each is the
identity token that operation's `required_capabilities()` returns, so dropping
one from a platform's set is how that platform says it does not implement the
operation:

| Token                        | Required by                              |
|------------------------------|------------------------------------------|
| `vendor.qdac.set_offset`     | `program.qdac.set_offset(...)`            |
| `vendor.qdac.set_trigger`    | `program.qdac.set_trigger(...)`           |
| `vendor.qdac.wait_trigger`   | `program.qdac.wait_trigger(...)`          |
| `vendor.qdac.play`           | `program.qdac.play(...)`                  |

Twelve waveform tokens, because `play` reaches the DAC through a bus and
waveform tokens live on bus profiles. `waveform.single` is the channel-kind
token that `play` always claims, and the other eleven are the per-class tokens
of the envelopes the waveform engine renders:

```python
sorted(t for t in QDAC_DEFAULT_V1.capabilities if t.startswith("waveform."))
# ['waveform.arbitrary', 'waveform.chained', 'waveform.cosine', 'waveform.flat_top',
#  'waveform.gaussian', 'waveform.ramp', 'waveform.sech', 'waveform.sine',
#  'waveform.single', 'waveform.snz', 'waveform.square', 'waveform.tukey']
```

There is no `waveform.iq` and no IQ-specific class token. QDAC is
single-channel, so an IQ envelope on a qdac bus is rejected on its per-class
token:

```python
from qprogram.waveforms import IQDrag
from qprogram_qdac import QProgram

base_cc = qp.CompilerCapabilities.from_profile("qprogram-base-v1")
caps = qp.PlatformCapabilities(
    bus={},
    platform=qp.BusCapabilities(rt=base_cc, host=base_cc),
    default_bus_profile=qp.BusCapabilities(rt=None, host=qdac_cc),
)

program = QProgram(label="iq-on-qdac")
program.qdac.play("flux_q0", IQDrag(0.5, 40, 8, 0.1))

print(qp.explain(program, caps))
```

```text
plan for 'iq-on-qdac' — errors: 1 · warnings: 0 · info: 0
body
└─ qdac.play "flux_q0" IQDrag(amplitude=0.5, duration=40, sigma=8, beta=0.1)  [--]       !! missing-capability: 'Play' requires capability 'waveform.iq_drag' which is not supported by 'qdac-default-v1' (host)
```

`[--]` in the domain column means no domain can run the node.

### Tokens the profile deliberately omits

`qdac-default-v1` carries no `block.*`, `sweep.*`, or `expr.*` tokens:

```python
[t for t in ("block.sweep", "sweep.linear", "expr.variable") if t in QDAC_DEFAULT_V1.capabilities]
# []
```

Those belong to the platform slot, not to a bus. Blocks always route to
`caps.platform`, and `expr.*` tokens are always checked against `caps.platform`
regardless of where the operation carrying them routes. `set_offset` with a
swept expression is the case that matters here:

```python
from qprogram_qdac.operations import SetOffset

program = QProgram()
bias = program.variable("bias")

sorted(SetOffset("flux_q0", bias).required_capabilities())
# ['expr.variable', 'vendor.qdac.set_offset']
sorted(SetOffset("flux_q0", bias * 0.5 + 0.1).required_capabilities())
# ['expr.binary_op', 'expr.constant', 'expr.variable', 'vendor.qdac.set_offset']
```

The `expr.*` half of that set is checked against the platform slot, which the
core `qprogram-base-v1` profile fills. That is why the qdac bus profile does not
need them.

## Limits

One limit, and the core validator does not check it:

| Limit          | Value | Meaning                                              |
|----------------|-------|------------------------------------------------------|
| `min_dwell_ns` | `100` | Floor on `play`'s `dwell`, below which the waveform engine's output interpolation breaks down. |

The validator reads four limit keys (`max_loop_nesting`, `max_parallel_loops`,
`max_measurements`, `min_wait_duration_ns`) and ignores every other key, so
`min_dwell_ns` is carried for platforms that enforce it themselves, either in
their compiler or through a predicate of their own. A `dwell` under the floor
validates clean:

```python
from qprogram.waveforms import Ramp

program = QProgram(label="fast-dwell")
program.qdac.play("flux_q0", Ramp(0.0, 1.0, 1000), dwell=1)

qp.validate(program, caps)[0]  # []
```

A device that knows its own floor tightens the value without republishing the
profile:

```python
tight = qp.CompilerCapabilities.from_profile(
    "qdac-default-v1",
    limit_overrides={"min_dwell_ns": 200},
)

tight.limits  # {'min_dwell_ns': 200}
```

`from_profile` also takes `extra_predicates=(...)`, which is where a platform
adds its own `min_dwell_ns` check.

## Predicates

The profile ships two predicates. They run against every visited node, and both
filter on node type first, so a program with no qdac operations is unaffected.

```python
len(QDAC_DEFAULT_V1.predicates)  # 2
```

One reclassifies, one rejects. A qdac operation that reads a loop-bound
variable pushes the loop that binds it host-side, which the core classifier
reports as a `forced-host` warning; a `set_trigger` that arms no outputs is
a hard `qdac.empty-trigger-outputs` error. The two subsections below give
the exact firing condition and the message for each.

### Swept variables force the loop host-side

**Fires when** the visited node is one of the four qdac operation classes
(`SetOffset`, `SetTrigger`, `WaitTrigger`, `Play`) **and** at least one variable
it references has a binding loop. The check walks `node.variables()`, which
descends into expression arguments and into waveform parameters, so a
`play(bus, Ramp(0.0, top, 1000))` is caught exactly like a
`set_offset(bus, bias)`.

**Yields** a soft `DomainConstraint`, one per distinct binding loop, with
`exclude={"rt"}` and a reason naming the operation and the variable. The
constraint targets the **binding loop block**, not the operation: it is the loop
that has to move host-side, while the operation itself stays classified as it
was. QDAC has no FPGA, so every parameter change goes through the host's
slow-control plane and cannot be a per-iteration register write.

**What the user sees** depends on the block's support before the constraint
applies.

With the wiring that matches the hardware, `rt=None` and the profile in the
`host` half, the loop is already host-side by op-children consensus. There is no
`{rt, host}` to reduce, so nothing surfaces at all:

```python
program = QProgram(label="flux-sweep")
bias = program.variable("bias", units="V")
with program.sweep(bias, qp.Range(0.0, 0.5, 0.05)):
    program.qdac.set_offset("flux_q0", bias)

print(qp.explain(program, caps))
```

```text
plan for 'flux-sweep' — errors: 0 · warnings: 0 · info: 0
body
└─ for bias in Range(start=0.0, stop=0.5, step=0.05):  [host]
   └─ qdac.set_offset "flux_q0" bias                   [host]
```

Put the profile in both halves of the bus slot and the operation becomes
`[rt|host]`. Now the constraint has something to subtract, the sweep drops to
`{host}`, and the core classifier reports it as a `forced-host` warning naming
the predicate's reason:

```python
both_halves = qp.PlatformCapabilities(
    bus={},
    platform=qp.BusCapabilities(rt=base_cc, host=base_cc),
    default_bus_profile=qp.BusCapabilities(rt=qdac_cc, host=qdac_cc),
)

for diagnostic in qp.validate(program, both_halves)[0]:
    print(diagnostic)
print(qp.explain(program, both_halves))
```

```text
[warning] forced-host: Block 'Sweep' falls back to host-side execution: qdac.SetOffset references loop-bound variable 'bias'; qdac has no FPGA, so the loop must dispatch host-side.. (at body[0])
plan for 'flux-sweep' — errors: 0 · warnings: 1 · info: 0
body
└─ for bias in Range(start=0.0, stop=0.5, step=0.05):  [host]     ~ forced-host: qdac.SetOffset references loop-bound variable 'bias'; qdac has no FPGA, so the loop must dispatch host-side
   └─ qdac.set_offset "flux_q0" bias                   [rt|host]
```

The diagnostic code is `forced-host` at `severity="warning"`, and it comes from
the core classifier rather than from the predicate. `~` is how `explain` marks a
warning. A program that only ever hits this warning still runs: the loop
dispatches from the host, one upload per iteration.

### An empty trigger-output set is an error

**Fires when** the visited node is a `SetTrigger` and its `outputs` tuple is
empty. Arming zero outputs configures a trigger that fires onto nothing.

**Yields** a hard `Diagnostic`, `severity="error"`, code
`qdac.empty-trigger-outputs`. It is an error in every domain, so no fallback
rescues it and the node's support ends up empty:

```python
program = QProgram(label="trigger-mistake")
program.qdac.set_trigger("flux_q0", 50, position="step")

for diagnostic in qp.validate(program, caps)[0]:
    print(diagnostic)
print(qp.explain(program, caps))
```

```text
[error] qdac.empty-trigger-outputs: SetTrigger has no outputs configured. Specify at least one output index, e.g. outputs={1} or outputs=[1, 2]. (at body[0])
plan for 'trigger-mistake' — errors: 1 · warnings: 0 · info: 0
body
└─ qdac.set_trigger "flux_q0" 50 position="step"  [--]       !! qdac.empty-trigger-outputs: SetTrigger has no outputs configured. Specify at least one output index, e.g. outputs={1} or outputs=[1, 2].
```

Naming at least one output clears it:

```python
program = QProgram(label="trigger-ok")
program.qdac.set_trigger("flux_q0", 50, position="step", outputs={1})

qp.validate(program, caps)[0]  # []
```

## Wiring the profile into a platform

`qdac-default-v1` is a **bus-slot** profile. It fills one half of one
`BusCapabilities`, and it fills nothing else:

- **Bus slots.** Attach it to the buses the QDAC drives, typically the flux
  buses of a transmon schema. Put it in the `host` half and leave `rt` as
  `None`: qdac has no FPGA, so no qdac operation belongs in a real-time
  sequencer program. Every qdac operation then classifies as `{host}` by
  construction.
- **Platform slot.** Fill it with the core `qprogram-base-v1` profile. That is
  where `block.*`, `sweep.*`, and `expr.*` live, and qdac contributes nothing
  there because it has no bus-less operations.
- **Default bus profile.** The fallback for raw-string buses and for buses with
  no `bus` entry. Point it at whichever vendor owns the unmapped buses.

A worked descriptor, with the QDAC on flux and a real-time vendor on drive and
readout:

```python
from qprogram.buses import BusSchema

schema = BusSchema.flux_tunable_transmon()
q = schema.q

qdac_slot = qp.BusCapabilities(
    rt=None,
    host=qp.CompilerCapabilities.from_profile("qdac-default-v1"),
)

# Stand-in for the fast vendor's own profile, spelled out so the example runs.
fast_cc = qp.CompilerCapabilities(
    profile="acme-rt-v1",
    version=(0, 1, 0),
    capabilities=frozenset({"op.play", "op.measure", "waveform.alias", "waveform.iq", "measure.fields.iq"}),
    limits={},
    predicates=(),
    vendor_versions={},
)
fast_slot = qp.BusCapabilities(rt=fast_cc, host=None)

platform_caps = qp.PlatformCapabilities(
    bus={
        ("q", "drive"): fast_slot,
        ("q", "readout"): fast_slot,
        ("q", "flux"): qdac_slot,
    },
    platform=qp.BusCapabilities(rt=base_cc, host=base_cc),
    default_bus_profile=qdac_slot,
)
```

The keys of `bus` are `(element_kind, bus_kind)` pairs, so `("q", "flux")`
covers `q[0].flux`, `q[1].flux`, and every other flux bus of the `q` element.

## Mixing QDAC with a real-time vendor

The shape that works puts the slow bias outside the fast inner loop: a host-side
sweep sets a flux point, and a real-time `average` block runs the pulses at that
point.

```python
program = QProgram(label="flux-spectroscopy", schema=schema)
bias = program.variable("bias", units="V")
with program.sweep(bias, qp.Range(-0.2, 0.2, 0.1)):
    program.qdac.set_offset(q[0].flux, bias)
    with program.average(1000):
        program.play(q[0].drive, "pi_pulse")
        program.measure(q[0].readout, "readout", "weights")

print(qp.explain(program, platform_caps))
```

```text
plan for 'flux-spectroscopy' — errors: 0 · warnings: 0 · info: 0
body
└─ for bias in Range(start=-0.2, stop=0.2, step=0.1):                   [host]
   ├─ qdac.set_offset q[0].flux bias                                    [host]
   └─ average 1000:                                                     [rt]
      ├─ play q[0].drive "pi_pulse"                                     [rt]
      └─ measure q[0].readout "readout" "weights" name="q0/readout/m0"  [rt]
```

Flatten that and it breaks. A host-only qdac operation and a real-time-only
pulse as siblings in one block leave the block with no domain that runs both:

```python
program = QProgram(label="mixed", schema=schema)
bias = program.variable("bias", units="V")
with program.sweep(bias, qp.Range(-0.2, 0.2, 0.1)):
    program.qdac.set_offset(q[0].flux, bias)
    program.play(q[0].drive, "pi_pulse")

print(qp.explain(program, platform_caps))
```

```text
plan for 'mixed' — errors: 1 · warnings: 0 · info: 0
body
└─ for bias in Range(start=-0.2, stop=0.2, step=0.1):  [--]       !! mixed-domain: Block 'Sweep' has op-children with incompatible domain singletons: [('SetOffset', ['host']), ('Play', ['rt'])]
   ├─ qdac.set_offset q[0].flux bias                   [host]
   └─ play q[0].drive "pi_pulse"                       [rt]
```

`mixed-domain` is a core diagnostic code, not a qdac one. The fix is structural:
wrap the real-time operations in their own block so the sweep sees a block-child
rather than an operation-child with a conflicting domain.

## Quick reference

| You want to ...                              | Use                                                             |
|----------------------------------------------|-----------------------------------------------------------------|
| Materialize the profile                       | `qp.CompilerCapabilities.from_profile("qdac-default-v1")`        |
| Attach it to a bus                            | `qp.BusCapabilities(rt=None, host=qdac_cc)`                      |
| Fill the platform slot                        | `qp.CompilerCapabilities.from_profile("qprogram-base-v1")`       |
| Tighten the dwell floor for one device        | `from_profile("qdac-default-v1", limit_overrides={"min_dwell_ns": 200})` |
| Add a check the profile does not make         | `from_profile("qdac-default-v1", extra_predicates=(my_pred,))`   |
| Ask whether a token is supported              | `qdac_cc.supports("vendor.qdac.play")`                           |
| See the plan and the diagnostics              | `qp.explain(program, caps)`, `qp.validate(program, caps)`        |

## Diagnostic codes

| Code                          | Severity  | Source                          |
|-------------------------------|-----------|---------------------------------|
| `qdac.empty-trigger-outputs`  | `error`   | This package's profile.          |
| `forced-host`                 | `warning` | Core, from this package's `DomainConstraint`. |
| `missing-capability`          | `error`   | Core, when a token is absent from the routed slot. |
| `mixed-domain`                | `error`   | Core, on a block with conflicting operation-children. |

## See also

- [Operations](operations.md) covers the four operations and which of their
  arguments can be swept.
- [Lowering onto hardware](../developer/lowering.md) covers what a platform does
  with a validated plan.
- The core guide's
  [capabilities page](https://qilimanjaro-tech.github.io/qprogram/guide/capabilities.html)
  covers the protocol itself: routing, the two domains, and every core
  diagnostic code.
