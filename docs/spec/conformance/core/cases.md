# Core Vector Cases

## valid.ndjson (9)

| # | Tests |
|---|---|
| 1 | `machine` body with full identity, location, capabilities, adapter provenance |
| 2 | `event` - core `cycle_complete` with payload |
| 3 | `event` - `error` with required `severity` |
| 4 | `event` with an `x-example` extension block (legal, included in checksum) |
| 5 | `process_run` shift summary with quantities and `event_seq_range` |
| 6 | `energy` interval from a CT clamp |
| 7 | `telemetry` stats mode |
| 8 | `telemetry` samples mode under `textile-dyeing/0.1` |
| 9 | envelope with `sig` present (syntactic check only) |

## invalid.ndjson (13)

| # | Rejected because |
|---|---|
| 1 | Unknown envelope field (spec s2: MUST reject) |
| 2 | Unknown `schema` value |
| 3 | `gateway_id` pattern violation (uppercase) |
| 4 | `seq` = 0 (starts at 1) |
| 5 | `ts` not ISO 8601 UTC millisecond with `Z` |
| 6 | Checksum mismatch - body altered after checksumming |
| 7 | `event_type` pattern violation |
| 8 | `error` event missing `severity` |
| 9 | Negative `energy.value` |
| 10 | `telemetry` mode=samples without `samples` |
| 11 | `process_run` missing `outcome` |
| 12 | `machine` missing `adapter` provenance |
| 13 | `x-` extension whose value is not an object |

Not statically testable here, validated in runtime suites: seq persistence
and monotonicity across restarts, energy interval non-overlap per
(machine, metric), dead-letter isolation, ts non-decrease within a boot
session.
