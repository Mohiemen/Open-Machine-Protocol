# OMP Core Schema Specification v0.1

| | |
|---|---|
| **Status** | Draft |
| **Location** | spec/omp-schema-v0.1.md |
| **Normative schemas** | spec/schemas/core/*.json (JSON Schema draft 2020-12) |
| **Last updated** | July 2026 |

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as described in RFC 2119. Where this prose and the JSON Schema files disagree, the JSON Schema files are normative and this document has a bug.

---

## 1. Overview

Every OMP message is an **envelope** wrapping exactly one **body** conforming to one of five core schemas:

| Schema | Cardinality | Purpose |
|---|---|---|
| `machine` | Once per machine, re-emitted on change and gateway restart | Identity and capability declaration |
| `event` | High frequency | Discrete occurrences |
| `process_run` | Per bounded unit of work | Batch/job genealogy |
| `energy` | Periodic | Utility consumption |
| `telemetry` | Periodic or streaming | Continuous sensor data |

Messages are UTF-8 JSON. On the wire and in buffers, messages are newline-delimited (NDJSON). A single message MUST NOT exceed 256 KiB serialized; telemetry producers SHOULD use statistical aggregation (section 8.3) rather than approach this limit.

## 2. The Envelope

```json
{
  "omp_version": "0.1.0",
  "profile": "textile-dyeing/0.1",
  "gateway_id": "gw-dhaka-f1-01",
  "machine_id": "f1-dye-jet02",
  "seq": 102331,
  "ts": "2026-07-24T09:14:03.221Z",
  "schema": "process_run",
  "body": { },
  "checksum": "a3f1...c9",
  "sig": "base64..."
}
```

| Field | Type | Req | Rules |
|---|---|---|---|
| `omp_version` | string | MUST | Semver of the core spec the message conforms to. Consumers MUST accept any same-major version. |
| `profile` | string | MUST | `{profile_name}/{profile_major.minor}`. The `generic` profile is always valid. |
| `gateway_id` | string | MUST | Globally unique per gateway install. Pattern `^[a-z0-9][a-z0-9-]{2,62}$`. |
| `machine_id` | string | MUST | Unique within the gateway. Same pattern as gateway_id. Stable across restarts and re-cabling. |
| `seq` | integer | MUST | Per (`gateway_id`, `machine_id`) monotonically increasing, starting at 1, never reused, persisted across gateway restarts. See section 3. |
| `ts` | string | MUST | ISO 8601 UTC with millisecond precision, `Z` suffix. Event time as best known to the gateway. See section 4. |
| `schema` | string | MUST | One of `machine`, `event`, `process_run`, `energy`, `telemetry`. |
| `body` | object | MUST | Conforms to the schema named above plus the declared profile's constraints. |
| `checksum` | string | MUST | Lowercase hex SHA-256 over the canonical serialization of `body` (section 5). |
| `sig` | string | MAY | Base64 Ed25519 signature over `gateway_id \|\| machine_id \|\| seq \|\| checksum`. |

Unknown envelope fields MUST be rejected by validators. Unknown body fields are governed by section 6 (extensions).

## 3. Sequence Semantics

- `seq` is assigned by the gateway at validation time, not by adapters.
- Consumers MUST deduplicate on the triple (`gateway_id`, `machine_id`, `seq`).
- A gap in `seq` observed by a consumer means messages exist that it has not received - either still in flight (at-least-once delivery, out-of-order is possible across exporter retries) or lost beyond the gateway's retention window. Consumers SHOULD track gaps and MAY query gateway health endpoints for retention boundaries.
- A `seq` regression (same triple, different checksum) is evidence of tampering or gateway misconfiguration and MUST be surfaced as an integrity alarm, not silently resolved.

## 4. Time

- `ts` is the gateway's best knowledge of when the underlying occurrence happened - the adapter MAY supply machine-reported time; otherwise the gateway stamps at receipt.
- Gateways SHOULD run NTP. Where NTP is unavailable, gateways MUST still guarantee that `ts` is non-decreasing per machine within a boot session and MUST report clock confidence in health data.
- Consumers MUST treat `seq` as the authority for ordering within a machine and `ts` as approximate wall-clock context. Cross-machine ordering by `ts` is inherently approximate.

## 5. Canonical Serialization (for checksums)

Checksum input is the `body` object serialized as JSON with - keys sorted lexicographically at every level, no insignificant whitespace, UTF-8 encoding, numbers in shortest round-trip form, no trailing zeros. This is JCS (RFC 8785). Implementations MUST use an RFC 8785 library or pass the canonicalization conformance vectors.

## 6. Extensions

- Any body object MAY contain fields whose names start with `x-` (e.g. `x-intelactory`). Their values MUST be objects.
- Core and profile validators MUST ignore the contents of extension blocks but MUST include them in checksum computation (they are part of `body`).
- Core and profile schemas MUST NOT define `x-` fields. Extension semantics are documented by their owners outside this repository.

## 7. Core Schemas

### 7.1 machine

Declares identity and capabilities. Emitted on gateway startup, on registry change, and SHOULD be re-emitted at least every 24 hours as a liveness anchor.

| Field | Type | Req | Notes |
|---|---|---|---|
| `machine_class` | string | MUST | From the declared profile's taxonomy (`generic` allows `unclassified`). |
| `make` | string | SHOULD | Manufacturer name, free text. |
| `model` | string | SHOULD | |
| `serial` | string | MAY | Manufacturer serial if known. |
| `year` | integer | MAY | Year of manufacture. |
| `location` | object | MUST | `{ "site": str, "area": str, "line": str, "station": str }`, all SHOULD be present, `site` MUST. |
| `capabilities` | array[string] | MUST | Which schemas this machine emits, e.g. `["event", "energy"]`. |
| `adapter` | object | MUST | `{ "name": str, "version": str }` - provenance of the data source. |
| `data_source` | string | MUST | One of `native` (controller protocol), `retrofit` (added sensors), `hybrid`. |

### 7.2 event

| Field | Type | Req | Notes |
|---|---|---|---|
| `event_type` | string | MUST | Core vocabulary (below) or the profile's vocabulary. Pattern `^[a-z][a-z0-9_]*$`. |
| `severity` | string | MUST for `error`/`alarm` types, MAY otherwise | `info`, `warning`, `error`, `critical`. |
| `run_id` | string | MAY | Associates the event with an open process run. |
| `payload` | object | MAY | Type-specific data as defined by core or profile. |
| `duration_ms` | integer | MAY | For events that close an interval (e.g. `stop` end). |

**Core event vocabulary** (valid under every profile):

| event_type | Meaning | Standard payload fields |
|---|---|---|
| `run_start` / `run_end` | Process run boundary | `run_id` MUST be set |
| `cycle_complete` | One unit cycle finished | `cycle_count` (cumulative), `cycle_time_ms` |
| `start` / `stop` | Machine began/ceased operating | `reason` (profile-defined codes or `unknown`) |
| `error` / `alarm` | Fault conditions | `code`, `message` |
| `state_change` | Controller state transition | `from_state`, `to_state` |
| `maintenance_flag` | Maintenance-relevant observation | `flag` |

Profiles extend this vocabulary (e.g. `needle_break`, `dosing_complete`, `tool_change`) and MUST NOT redefine core types.

### 7.3 process_run

The genealogy unit. A run is opened by `run_start`, closed by `run_end`, and summarized by exactly one `process_run` message emitted at close (or at abort).

| Field | Type | Req | Notes |
|---|---|---|---|
| `run_id` | string | MUST | Unique within the machine. SHOULD be globally unique (UUIDv7 recommended). |
| `run_type` | string | MUST | `batch`, `job`, `cycle_group`, `shift`, or profile-defined. |
| `program_ref` | string | MAY | Recipe, NC program, or work order reference as known to the machine. |
| `start_ts` / `end_ts` | string | MUST | ISO 8601 UTC. |
| `outcome` | string | MUST | `completed`, `aborted`, `failed`, `unknown`. |
| `phases` | array[object] | SHOULD | `{ "name": str, "start_ts": str, "end_ts": str, "params": obj }`. Phase names and params are profile-defined. |
| `quantities` | array[object] | SHOULD | `{ "name": str, "value": num, "unit": str }`, e.g. pieces produced, fabric kg, defects. |
| `event_seq_range` | object | SHOULD | `{ "first": int, "last": int }` - the envelope seq range of events belonging to this run. This is the field that lets a DPP claim cite its evidence. |

### 7.4 energy

| Field | Type | Req | Notes |
|---|---|---|---|
| `metric` | string | MUST | `kwh`, `water_l`, `steam_kg`, `air_m3`, `gas_m3`, or profile-defined. |
| `value` | number | MUST | Consumption during the interval, not a meter total. MUST be >= 0. |
| `interval` | object | MUST | `{ "start_ts": str, "end_ts": str }`. Intervals per (machine, metric) MUST NOT overlap. |
| `source` | string | MUST | `native`, `ct_clamp`, `submeter`, `estimated`. Consumers weigh evidence accordingly. |
| `run_id` | string | MAY | Attribution to a process run. |

### 7.5 telemetry

| Field | Type | Req | Notes |
|---|---|---|---|
| `channel` | string | MUST | e.g. `bath_temp`, `spindle_vibration_rms`. Profile-recommended names SHOULD be used. |
| `unit` | string | MUST | UCUM unit string (`Cel`, `Hz`, `A`). |
| `mode` | string | MUST | `samples` or `stats`. |
| `samples` | array | MUST if mode=samples | `{ "t": iso8601, "v": num }` pairs. |
| `stats` | object | MUST if mode=stats | `{ "start_ts", "end_ts", "min", "max", "avg", "count" }`. |
| `run_id` | string | MAY | |

Producers SHOULD prefer `stats` mode above 1 Hz effective rates.

## 8. Validation and Failure Rules

1. Gateways MUST validate every message against the core schema AND the declared profile before buffering.
2. Invalid messages MUST go to the dead-letter store with the validation error attached and MUST NOT be exported as valid data.
3. Validators MUST reject unknown envelope fields, unknown `schema` values, malformed patterns, and non-conformant profile references.
4. A message valid under core but invalid under its declared profile is invalid.
5. Conformance vectors in `spec/conformance/` are the executable definition of this section. An implementation that passes all vectors is conformant for the covered behavior.

## 9. Versioning

- Core and each profile version independently under semver.
- **Additive** (new optional fields, new event types, new metrics) - minor bump.
- **Breaking** (removing/renaming fields, tightening requirements, changing semantics) - major bump, RFC with 28-day window, migration guide required.
- Consumers MUST accept unknown *profile* event types under a known profile major version (forward compatibility within major), treating them as opaque events.

## 10. What This Spec Deliberately Does Not Define

- Operator identity (open question, likely profile or extension territory)
- Quality/inspection results beyond `quantities` (candidate for a future core schema, needs RFC)
- Machine control messages (constitutionally excluded)
- Transport security (exporter concern, see security architecture)
