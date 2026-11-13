# qprogram-qdac review contract

Shared core v0.2 (Qilimanjaro Software), a draft until the software leads agree it. Copied verbatim, followed by qprogram-qdac additions. Applies to humans and agents. AI review is advisory: a qualified human reads every line of the same revision before merge.

## Findings
- Each finding gives `path:line` and quotes the line, then the trigger, the consequence, the evidence and a concrete next step. No citation, no finding.
- Separate confirmed defects from questions and missing evidence. Recheck earlier findings on the current revision and state the inspected scope.
- Review on two axes: standards (`CODING_STANDARDS.md`, citing the section) and spec (the linked ticket, PRD or TRD: missing, extra, wrong; quote the spec line).
- Green CI is evidence, not a verdict: say what it covers and what it misses.

## Severity
Lead with the highest.
- **blocker**: wrong results, data loss, a security hole, or a broken invariant from AGENTS.md. Fix before merge.
- **major**: a likely bug, or a design problem the next change will trip over. Fix, or justify in the PR.
- **minor**: worth fixing, not blocking.
- **nit**: taste. At most 3 per review; drop the rest.

## qprogram-qdac additions
- **Right repository.** Only what a QDAC alone can do belongs here. A change any backend would want, or one to the AST, the validator or the `.qp` format, belongs in the core `qprogram` (`docs/developer/contributing.md`, "Before you start").
- **Whole operation.** A new or changed operation carries every item in `docs/developer/contributing.md`, "The checklist for a new operation": the code edits, one test per module, the guide pages and the `members:` lists in `docs/reference/api.md`.
- **Wire form.** A change to an operation's meaning on the wire needs a major bump and a migration registered with `qp.register_vendor_migration("qdac", ...)`, or a PR that says why none is needed; adding an operation is a minor bump. Without either, it is a blocker, because saved `.qp` files stop loading or load with the wrong meaning.
- **Profile.** A claim that something runs real-time or host-side is checked against `src/qprogram_qdac/profiles.py`. A new or changed predicate has a test that asserts its diagnostic code.
- **Docs.** Docs changes follow `.claude/skills/qprogram-docs/SKILL.md`; its checker and `zensical build --strict` pass.
- **Public repository.** No internal links, hostnames, customer data or measurement data in the diff, the PR text or the commit messages.
- **Units.** Values follow the convention in CODING_STANDARDS.md additions; check every conversion where a value leaves this repo (compiler, driver, instrument).
- **Parity.** Any numeric change ships before-and-after output, with each difference explained, from a synthetic input that reaches the changed code: the `.qp` text `qprogram.dumps` writes for a program that uses the changed operation, and the diagnostics `qprogram.validate` returns against `qdac-default-v1`. The repo has no example data or reference set.
