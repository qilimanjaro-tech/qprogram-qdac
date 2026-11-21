# QProgram QDAC

The QDevil QDAC vendor extension for the QProgram DSL: the `qdac` operations, their capability profile and their `.qp` text form.

Terms shared across Qilimanjaro's stack are in the [shared glossary](https://github.com/qilimanjaro-tech/claude-skills/blob/main/onboarding/qilimanjaro-agent-starter-kit/org-context/qilimanjaro-glossary.md); terms of the core DSL (AST, capability token, `.qp` format) are defined in the core `qprogram` documentation. This file holds QProgram QDAC's own.

## Language

**Vendor namespace**:
The name `qdac` under which this package attaches its operations to a QProgram, reached as `program.qdac`, and which prefixes their `.qp` statements and capability tokens.

**QDAC operation**:
One of the four AST nodes this package adds: `set_offset`, `play`, `set_trigger` and `wait_trigger`.

**Waveform engine**:
The sequencer in a QDAC channel that emits an uploaded envelope with a given dwell, delay, repetition count and stepping mode; `play` programs it.

**Dwell**:
How long the waveform engine holds each sample of an envelope, an integer number of µs with a floor of 2.

**Trigger network**:
The chassis trigger lines that `set_trigger` arms and `wait_trigger` waits on, so a QDAC sequence lines up with instruments on other buses.

**Capability profile**:
`qdac-default-v1`, the declaration of what one QDAC channel supports: its capability tokens and the predicates a program is validated against.

**Require line**:
The `require qdac <major>.<minor>` line in a `.qp` file header, naming the vendor protocol version the file was written against.
_Avoid_: Version header (that is the `#!QProgram` line)
