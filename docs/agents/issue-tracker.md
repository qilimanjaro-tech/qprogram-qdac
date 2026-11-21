# Issue tracker: GitHub issues and Linear team QHC

TODO(human): confirm the tracker with the maintainers. This file records what the repository shows on 13 Nov 2026, not an agreed rule.

- **GitHub Issues** on `qilimanjaro-tech/qprogram-qdac` is the public intake and backlog. The templates in `.github/ISSUE_TEMPLATE/` file a Bug, a Feature or a Task, marked by the GitHub issue type and a `[Bug]: `, `[Feature]: ` or `[Task]: ` title prefix, not by a label. Issue #7 is a `[Task]`; its body also names an SDK ticket in Linear.
- **Linear, team QHC** (`QHC-####`) holds the work the QHC team picks up. Such a PR branches as `qhc-####-<topic>`, is titled `[QHC-####] Name` and links the ticket, as PR #8 (QHC-1845) did.
- PRs #1 to #6 link no ticket in either tracker.

## Conventions

- **Read a GitHub issue:** `gh issue view <number> --json number,title,body,labels,comments`.
- **List GitHub issues:** `gh issue list --state open --json number,title,labels`, with `--label` and `--state` filters.
- **Read a Linear ticket:** use the Linear tools (for example the Linear MCP server's `get_issue`) on team QHC, by its identifier (`QHC-1845`).
- **Create, comment, label or close:** show the human the target tracker, the title and the body, and get a yes first. Write nothing internal in a GitHub issue: the repository is public.
- **Branches and PRs:** see `## Branches and PRs` in `AGENTS.md`.

## Pull requests as a triage surface

**PRs as a request surface: no.** External pull requests are not part of the triage queue. Set it to `yes` if the team starts triaging drive-by PRs.

## When a skill says "publish to the issue tracker"

Ask the human which tracker. Default to a GitHub issue from the matching template (Bug, Feature or Task); use a Linear ticket on team QHC when the QHC team takes the work.

## When a skill says "fetch the relevant ticket"

Read the GitHub issue (`#<n>`) or the Linear ticket (`QHC-####`) the human or the PR names, as in **Conventions** above.
