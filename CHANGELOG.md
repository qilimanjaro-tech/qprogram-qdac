# Changelog

Notable changes to QProgram QDAC, newest first. Each entry starts life as a news fragment under `changelog/`, and `towncrier build` assembles the fragments into a release section here. See [Contributing](https://qilimanjaro-tech.github.io/qprogram-qdac/developer/contributing.html) for how to add one.

<!-- towncrier release notes start -->

## 0.2.0 (2026-09-08)

This release requires qprogram 0.2, which is what a `require qdac` line is now read against. One thing follows from the core release rather than from anything here: a `.qp` file written before it no longer loads, because its `#!QProgram 1.0` header reads as a later version than the `0.2` the core writes now, and nothing runs backwards. A file whose header is current is carried up instead, since a `require qdac` line naming an earlier major is migrated rather than refused.

### Changed

- The `require qdac <major>.<minor>` line is read by the rule the core DSL applies to a file header, which needs qprogram 0.2. A line asking for more than the installed package provides is still refused, and the message now names what to install: `file requires qdac 1.0, newer than the installed qdac 0.2.0 — install qdac 1.0 or newer`. A line carrying a patch (`require qdac 0.1.0`) is refused rather than rounded down, since a patch release of this package changes code and never the wire form. A line naming an earlier major loads instead of being refused, so a release that changes an operation's wire form registers a rewrite for it with `qp.register_vendor_migration("qdac", "<major>.<minor>")` and the files users already have go on loading. Nothing in this package's own API changes. ([PR #4](https://github.com/qilimanjaro-tech/qprogram-qdac/pull/4))


## 0.1.0 (2026-08-25)

### Added

- First release. QProgram QDAC adds the `qdac` vendor namespace to the core DSL, covering the QDevil QDAC, a slow high-precision DAC used most often for flux biasing. Importing the package is what turns it on.
- Four operations covering DC offsets, the waveform engine, and the chassis trigger network.
- A capability profile describing what a QDAC channel can do, so a program is validated against the hardware before it is run.
- `.qp` serialization for everything the package adds, registered so that a file naming the `qdac` vendor resolves without the caller importing this package first.
