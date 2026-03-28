---
name: adsb-feeder-healthcheck
description: Convert the CopterSpotter ADS-B feeder healthcheck runbook into a reusable MongoDB MCP workflow for checking feeder activity, feeder last-seen timestamps, and fixed-range feeder history across one or two ADS-B collections.
---

# ADS-B Feeder Healthcheck

This skill is a direct conversion of the CopterSpotter runbook in `references/source-runbook-notes.md`. Preserve that workflow first, then generalize only the repo-specific defaults so the same process works from `copterspotter`, `CopterFeeder`, or another ADS-B repo.

## Use This Skill When

- You need to check which feeders have sent data recently.
- You need the last-seen timestamp per feeder across all available ADS-B data.
- You need to find feeders whose names match a substring.
- You need a reproducible feeder report for a fixed historical range.
- The workflow should use MongoDB MCP aggregations instead of ad hoc shell or database commands.

## Workflow

### 1. Discover repo defaults before asking

Read the current repo in this order:

1. `AGENTS.md`
2. Repo docs or runbooks
3. Code or config that names the Mongo database, collections, and field paths

Use `references/repo-discovery.md` for the expected cues in `copterspotter`, `CopterFeeder`, or an unfamiliar repo.

If the repo clearly establishes the Mongo target, continue without asking the user.

If the repo does not clearly establish the Mongo target, ask for:

- database name
- base collection name
- optional secondary collection name
- feeder field path
- timestamp field path

### 2. Keep the original query semantics

Match the source runbook behavior. Do not broaden the semantics unless the user explicitly asks for a different report.

Supported query modes:

- feeders active in the last `N` hours
- last-seen per feeder across all data
- last-seen for feeders matching a substring
- fixed historical date range

Use `references/query-recipes.md` for the aggregation templates. Replace placeholder collection names and field paths before sending the MCP call.

### 3. Prefer MongoDB MCP aggregations

- Run the aggregation on the primary collection.
- Use `$unionWith` for the optional secondary collection when one exists.
- If the repo only confirms one collection, remove the `$unionWith` stage and say so in the report.
- Keep the pipeline shape aligned with the source runbook.

### 4. Return a complete report

Every final answer should include:

- database used
- collection or collections used
- feeder field path used
- timestamp field path used
- query mode used
- time window or fixed range used
- feeder filter used, if any
- result summary with feeder names, counts, and latest timestamps

## Guardrails

- The source runbook wins when there is ambiguity.
- Do not assume `HelicoptersofDC-2023`, `ADSB`, or `ADSB-mil` unless the repo or the user confirms them.
- Do not assume `properties.feeder` or `properties.jsDate` unless the repo or the user confirms them.
- Prefer discovery from repo docs and code before asking the user for missing values.
- If field types are unclear, stop and confirm before writing a Mongo aggregation.
- When editing this skill later, keep `references/source-runbook-notes.md` aligned with the runbook it was derived from.

## Resources

- `references/source-runbook-notes.md`: mapping from the CopterSpotter runbook to this skill
- `references/repo-discovery.md`: discovery order and repo-specific cues
- `references/query-recipes.md`: aggregation templates with placeholders
