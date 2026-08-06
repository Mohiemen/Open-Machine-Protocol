# OMP Profile Specification v0.1

| | |
|---|---|
| **Status** | Draft |
| **Location** | spec/profiles/PROFILE-SPEC.md |
| **Companion** | Core Schema Specification v0.1 (spec/omp-schema-v0.1.md) |
| **Worked example** | textile-dyeing profile, included in section 8 |
| **Last updated** | July 2026 |

RFC 2119 keywords apply. Where prose and a profile's JSON files disagree, the JSON files are normative.

---

## 1. What a Profile Is

A Domain Profile specializes the industry-neutral core for one industry or machine family. It answers the questions the core deliberately refuses to answer - what kinds of machines exist here, what events they produce, what a process run's phases mean, and what telemetry matters.

A profile is intentionally small. If writing one takes more than a few focused days for a domain expert, either the profile is overreaching or this specification has failed.

## 2. What a Profile MUST Define

Every profile is a directory under `spec/profiles/{name}/` containing:

```
spec/profiles/textile-dyeing/
├── PROFILE.md              # Human-readable spec (this structure)
├── profile.json            # Machine-readable manifest
├── machine-classes.json    # Taxonomy
├── events.json             # Event vocabulary
├── phases.json             # Process run phase definitions
├── telemetry.json          # Recommended channels
└── conformance/            # Valid and invalid test vectors
```

| Artifact | Defines |
|---|---|
| **Manifest** | Profile name, semver, owners (working group), core version compatibility |
| **Machine class taxonomy** | Closed list of `machine_class` values with definitions |
| **Event vocabulary** | Profile event types extending the core set, each with payload schema |
| **Phase definitions** | Named phases for `process_run.phases[]` with their `params` schemas |
| **Telemetry channels** | Recommended channel names with UCUM units |
| **Conformance vectors** | Executable definition of all the above |

## 3. Rules Binding All Profiles

1. A profile MUST NOT redefine, restrict, or shadow core event types, core fields, or envelope semantics.
2. A profile MUST NOT contain vendor-specific or platform-specific fields. Vendor realities are handled by adapters mapping into profile vocabulary; platform needs go in `x-*` extensions.
3. All profile identifiers (classes, event types, phases, channels) MUST match `^[a-z][a-z0-9_]*$`.
4. Every profile event type MUST have a payload schema, even if empty. Undocumented payloads are non-conformant.
5. Profiles version independently under semver. Adding classes, events, phases, or channels is minor. Removing or changing semantics is major and requires an RFC with migration guidance.
6. A profile MUST be implementable by at least one adapter or simulator at acceptance time - no speculative profiles.
7. Profile working groups MUST include at least 2 practitioners from the target industry (GOVERNANCE.md 6.2).

## 4. Design Guidance (SHOULD, learned the hard way elsewhere)

- **Model what machines report, not what managers wish for.** If no dyeing controller reports "shade accuracy," it does not belong in the profile. Derived judgments live upstream in platforms.
- **Closed vocabularies beat free text.** Every free-text field is a future data-cleaning project in someone's platform. Prefer enumerations plus an `other` escape hatch with a `detail` string.
- **Name from the operator's floor language, then translate.** The identifier is `needle_break` because that is what a sewing line calls it. Profile docs SHOULD include local-language glossaries (Bangla first for the textile profiles).
- **Phases are the audit skeleton.** Choose phase boundaries that map to what a compliance claim would need to prove - temperature curves, hold durations, dosing points.
- **When in doubt, leave it out.** Anything can be added in a minor release. Removal costs a major.

## 5. Relationship Between Profiles and Adapters

An adapter declares which profiles it can emit. The mapping burden sits entirely in the adapter - a Sedo Treepoint adapter translates controller-specific phase codes into `textile-dyeing` phase names; the profile never mentions Sedo. This keeps profiles stable while adapters churn.

One machine MAY be served by multiple data sources under one `machine_id` (e.g. native controller events plus a retrofit CT clamp for energy), declared via `machine.json` `data_source: hybrid`.

## 6. The generic Profile

`generic/0.1` is the universal fallback - core event vocabulary only, `machine_class: unclassified` permitted, no phases or channels defined. Its purpose is to guarantee that a machine can stream conformant data on day one, before its industry has a profile. Gateways MUST ship with `generic` available.

## 7. Profile Lifecycle

| Stage | Meaning | Requirements |
|---|---|---|
| `draft` | Under RFC discussion | RFC open |
| `active` | Accepted, in production use | RFC accepted, working group formed, conformance vectors, one implementation |
| `deprecated` | Superseded, still valid | Successor named, sunset date >= 12 months out |
| `archived` | No longer accepted by validators by default | Explicit flag required to process |

## 8. Worked Example - the textile-dyeing Profile v0.1

The following is the substantive content of the first non-trivial OMP profile, serving as both a real deliverable and the template for future profiles.

### 8.1 Machine classes

| machine_class | Definition |
|---|---|
| `jet_dyeing` | Jet/overflow dyeing machine, rope form |
| `winch_dyeing` | Winch/beck dyeing machine |
| `jigger` | Jigger dyeing, open-width |
| `pad_dyeing` | Continuous padding range |
| `soft_flow` | Soft-flow/airflow dyeing machine |
| `washing` | Garment/fabric washing machine |
| `hydro_extractor` | Centrifugal extraction |
| `dryer` | Drying machine (tumble, relax, stenter-dry duty) |
| `other` | Requires `detail` in machine.json extension of make/model |

### 8.2 Event vocabulary (extends core)

| event_type | Payload | Notes |
|---|---|---|
| `phase_start` / `phase_end` | `{ "phase": str }` | Phase names from 8.3 |
| `dosing_start` / `dosing_complete` | `{ "tank": str, "chemical_ref": str, "target_amount": num, "unit": str, "actual_amount": num? }` | `chemical_ref` is the factory's own reference code, never a free-text chemical name |
| `temp_setpoint_change` | `{ "target_c": num, "gradient_c_per_min": num? }` | |
| `hold_start` / `hold_end` | `{ "target_c": num, "planned_min": num }` | |
| `sample_taken` | `{ "phase": str }` | Lab sample pulled for shade check |
| `addition` | `{ "reason": str enum [shade_correction, leveling, other], "detail": str? }` | Mid-process manual addition, a key quality signal |
| `machine_fault` | `{ "code": str, "subsystem": str enum [pump, heater, dosing, drive, sensor, other] }` | Specializes core `error` |

### 8.3 Phase definitions (for process_run.phases[])

| phase | params schema |
|---|---|
| `load` | `{ "fabric_kg": num, "liquor_ratio": num? }` |
| `pretreat` | `{ "type": str enum [scour, bleach, enzyme, other] }` |
| `heat` | `{ "from_c": num, "to_c": num, "gradient_c_per_min": num }` |
| `hold` | `{ "temp_c": num, "duration_min": num }` |
| `dose` | `{ "chemical_ref": str, "amount": num, "unit": str }` |
| `cool` | `{ "from_c": num, "to_c": num, "gradient_c_per_min": num }` |
| `rinse` | `{ "cycles": int, "temp_c": num? }` |
| `drain` | `{}` |
| `unload` | `{}` |

A completed dye batch's `process_run` therefore carries the full temperature/time/dosing skeleton - exactly the data a Digital Product Passport process claim needs, in verifiable form via `event_seq_range`.

### 8.4 Recommended telemetry channels

| channel | unit (UCUM) | Notes |
|---|---|---|
| `bath_temp` | `Cel` | Primary process variable |
| `bath_ph` | `[pH]` | Where probe fitted |
| `liquor_flow` | `L/min` | Jet/soft-flow machines |
| `steam_valve_pct` | `%` | Heating demand proxy |
| `motor_current` | `A` | Native or CT clamp |
| `water_meter_flow` | `L/min` | Submeter where fitted |

### 8.5 Quantities (recommended names for process_run.quantities[])

`fabric_kg`, `water_l_total`, `steam_kg_total`, `kwh_total`, `chemicals_dosed_count`, `additions_count`, `rework_flag` (0/1).

### 8.6 Conformance vectors

The profile ships vectors covering - a complete valid batch (load through unload), a batch with a mid-process `addition`, an aborted batch (`outcome: aborted` with truncated phases), and invalid cases (unknown phase name, dosing event missing `chemical_ref`, temperature params with wrong types).

---

## 9. Profile Authoring Checklist

- [ ] Working group formed, 2+ industry practitioners named
- [ ] RFC opened with motivation and scope boundaries
- [ ] Machine class taxonomy (closed list + other)
- [ ] Event vocabulary, every type with payload schema
- [ ] Phase definitions with params schemas
- [ ] Telemetry channel recommendations with UCUM units
- [ ] Local-language glossary where relevant
- [ ] Conformance vectors, valid and invalid
- [ ] One adapter or simulator emitting the profile
- [ ] omp-simulate scenario contributed (`--profile {name}`)
