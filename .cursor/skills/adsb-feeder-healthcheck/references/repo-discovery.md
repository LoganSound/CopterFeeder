# Repo discovery

Use repo evidence before asking the user for Mongo details.

## Discovery order

1. Read `AGENTS.md`.
2. Read repo docs or runbooks related to ADS-B, Mongo, routes, or operations.
3. Search code for:
   - database names
   - collection names
   - `properties.feeder`
   - `properties.jsDate`
   - `$unionWith`
   - ADS-B route or ingestion code

If the repo still does not establish the target clearly, ask for the missing database, collection, and field-path values.

## CopterSpotter cues

- `copterspotter/.cursor/rules/adsb-feeder-healthcheck.mdc`
  - Establishes the original runbook behavior
  - Names `HelicoptersofDC-2023`, `ADSB`, `ADSB-mil`, `properties.feeder`, and `properties.jsDate`
- `copterspotter/.cursor/rules/adsb-routes.mdc`
  - Links to the feeder healthcheck runbook as an operational runbook
- `copterspotter/routes/adsbLookupCore.js`
  - Confirms the `ADSB` plus `ADSB-mil` aggregation pattern
  - Confirms `properties.jsDate` usage in Mongo queries
- `copterspotter/routes/adsbRoutes.js`
  - Repeats the primary-plus-secondary collection pattern with `$unionWith`

For `copterspotter`, the runbook is the strongest evidence source. Use it first.

## CopterFeeder cues

- `CopterFeeder/AGENTS.md`
  - Confirms the repo writes rotorcraft data into a MongoDB-backed API flow
- `CopterFeeder/fcs.py`
  - Confirms the database name `HelicoptersofDC-2023`
  - Confirms collection selection between `ADSB` and `ADSB-mil`

`CopterFeeder` does not expose the feeder healthcheck runbook itself, so inspect code before assuming field paths. If field-path evidence is missing in the repo, ask the user to confirm them.

## Unknown repo checklist

Look for one or more of these patterns:

- `db.collection("...")`
- `myclient["..."]`
- `$unionWith`
- `properties.feeder`
- `properties.jsDate`
- feeder identifiers written during ingestion
- report or healthcheck docs that mention ADS-B or feeder recency

If you only find partial evidence, state what was discovered and ask only for the missing values.
