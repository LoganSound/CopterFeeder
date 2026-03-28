# Source runbook mapping

This skill is derived from `copterspotter/.cursor/rules/adsb-feeder-healthcheck.mdc`.

## Section mapping

- Runbook description and prerequisites:
  - Skill sections `Use This Skill When`, `Workflow`, and `Guardrails`
  - Converted from repo-specific defaults into a discovery-first workflow
- Query 1: feeders with data in last N hours:
  - Skill query mode `feeders active in the last N hours`
  - Pipeline template in `query-recipes.md` under `Rolling window`
- Query 2a: last date per feeder across all data:
  - Skill query mode `last-seen per feeder across all data`
  - Pipeline template in `query-recipes.md` under `All feeders`
- Query 2b: feeders matching a name pattern:
  - Skill query mode `last-seen for feeders matching a substring`
  - Pipeline template in `query-recipes.md` under `Substring match`
- Query 3: fixed date range:
  - Skill query mode `fixed historical date range`
  - Pipeline template in `query-recipes.md` under `Fixed range`
- Runbook tips:
  - Skill guidance to run against the primary collection and use `$unionWith` for the optional secondary collection
  - Skill reminder that `$dateSubtract` requires MongoDB 5.0 or newer

## What changed during conversion

- Repo defaults are now discovered instead of assumed.
- Collection names and field paths are parameterized with placeholders.
- The reporting requirements are explicit so final answers always surface the exact database, collection set, and filter choices used.

## What must stay aligned

- The four supported query modes
- `$unionWith`-based aggregation across one or two collections
- Grouping by feeder and reporting the latest timestamp per feeder
- The rule that runbook behavior wins if generalization would change semantics
