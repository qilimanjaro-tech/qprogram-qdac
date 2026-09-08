# Changelog

Notable changes to QProgram QDAC, newest first. Each entry starts life as a news fragment under `changelog/`, and `towncrier build` assembles the fragments into a release section here. See [Contributing](https://qilimanjaro-tech.github.io/qprogram-qdac/developer/contributing.html) for how to add one.

<!-- towncrier release notes start -->

## 0.1.0 (2026-08-25)

### Added

- First release. QProgram QDAC adds the `qdac` vendor namespace to the core DSL, covering the QDevil QDAC, a slow high-precision DAC used most often for flux biasing. Importing the package is what turns it on.
- Four operations covering DC offsets, the waveform engine, and the chassis trigger network.
- A capability profile describing what a QDAC channel can do, so a program is validated against the hardware before it is run.
- `.qp` serialization for everything the package adds, registered so that a file naming the `qdac` vendor resolves without the caller importing this package first.
