# OMP Profile - textile-sewing v0.1

| | |
|---|---|
| **Status** | Draft - pending RFC and working-group formation (GOVERNANCE.md 6.2); published now because the profile is exercised throughout the project's examples and simulator |
| **Location** | spec/profiles/textile-sewing/PROFILE.md |
| **Extends** | Core Schema Specification v0.1 |
| **Governed by** | [Profile Specification](../PROFILE-SPEC.md) - all rules in its section 3 bind this profile |
| **Last updated** | July 2026 |

Covers sewing and garment-assembly floors - sewing machines and the adjacent
machine classes a sewing line depends on (cutting, fusing, pressing). Written
from the floor's language first: the identifier is `needle_break` because that
is what a sewing line calls it.

Machine-readable artifacts (`profile.json`, `machine-classes.json`,
`events.json`, `phases.json`, `telemetry.json`, `conformance/`) are an M1
roadmap item; until they land, this document is the profile's definition.

---

## 1. Machine Classes

Closed list plus `other`. Classes distinguish what changes a consumer's
interpretation of the data, not vendor catalog variants.

| machine_class | Definition |
|---|---|
| `lockstitch` | Single/multi-needle lockstitch machine (the plain sewer) |
| `overlock` | Overlock/serger, edge finishing |
| `coverstitch` | Coverstitch/flatlock machine |
| `bartack` | Bartack/tacking machine, fixed-cycle |
| `buttonhole` | Buttonhole machine, fixed-cycle |
| `button_attach` | Button attaching machine, fixed-cycle |
| `cutting` | Fabric cutting (straight knife, band knife, automated cutter) |
| `fusing` | Fusing press (interlining bonding) |
| `ironing_press` | Pressing/finishing station with measurable duty |
| `other` | Anything else on the floor; identify via `make`/`model` in machine.json |

## 2. Event Vocabulary (extends core)

Per PROFILE-SPEC rule 4, every event type carries a payload schema, even if
empty. Core types (`cycle_complete`, `start`, `stop`, `error`, etc.) apply
unchanged and are never redefined here. Only events that real controllers or
retrofit sensors actually report are included - operator-behavior judgments
(efficiency, skill grades) are platform territory.

| event_type | Payload | Notes |
|---|---|---|
| `needle_break` | `{ "needle_position": int? }` | Reported by machines with needle sensors; retrofit optical counters cannot infer it |
| `thread_break` | `{ "thread_path": str enum [needle, bobbin, looper, unknown]? }` | Thread-break sensor equipped machines |
| `bobbin_change` | `{}` | Bobbin-out or bobbin-change signal where sensed |
| `stitch_count_update` | `{ "stitch_count": int }` | Cumulative stitches, from controllers that report it; distinct from `cycle_complete` (cycles) |
| `program_change` | `{ "program_ref": str }` | Pattern/program selection on programmable machines (bartack, buttonhole, electronic lockstitch) |
| `speed_setpoint_change` | `{ "target_spm": num }` | Setpoint in stitches per minute, where the controller reports it |
| `press_cycle` | `{ "temp_c": num?, "duration_s": num?, "pressure_kpa": num? }` | One fusing/pressing cycle with its actual parameters - the compliance-relevant event for `fusing` and `ironing_press` |
| `machine_fault` | `{ "code": str, "subsystem": str enum [motor, needle_bar, thread_path, trimmer, pneumatics, sensor, other] }` | Specializes core `error`, same pattern as textile-dyeing |

## 3. Process Runs and Phases

Sewing is cycle-based, not batch-phase-based - a garment operation is seconds
long and machines do not report phase structure within it. This profile
therefore defines **no phase vocabulary** (an empty `phases.json`), which is a
deliberate modeling decision, not an omission:

- `process_run` is used at the aggregation levels the floor actually manages:
  `run_type: shift` (one machine's shift summary) and `run_type: cycle_group`
  (a bundle/style lot on one machine, opened and closed by `run_start` /
  `run_end` where the adapter can detect style changes via `program_change`).
- `program_ref` carries the style/operation reference as known to the machine.
- Anything finer-grained (operation sequencing across a line, SAM targets,
  line balancing) is derived upstream by platforms from events - per the
  "model what machines report" rule.

The contrast with textile-dyeing (rich phase skeleton) is intentional and is
the worked demonstration that phases are optional per profile.

## 4. Recommended Telemetry Channels

| channel | unit (UCUM) | Notes |
|---|---|---|
| `motor_current` | `A` | Native or CT clamp; run/idle inference source |
| `stitch_rate` | `Hz` | Instantaneous stitch frequency where reported |
| `vibration_rms` | `m/s2` | Retrofit accelerometer, condition monitoring |
| `press_temp` | `Cel` | Fusing/pressing platen temperature |

## 5. Quantities (recommended names for process_run.quantities[])

`pieces_produced`, `cycles_total`, `stitches_total`, `defects_flagged`,
`rework_count`, `kwh_total`, `runtime_min`, `idle_min`.

## 6. Data Source Reality

Most of the world's sewing machines are mechanically excellent and digitally
mute - this profile is expected to be emitted more often by retrofit nodes
(`data_source: retrofit`: optical cycle counters emitting `cycle_complete`,
CT clamps emitting `energy` and inferred `start`/`stop`) than by native
controllers. Events in section 2 that require native sensing simply do not
appear in retrofit-only streams; consumers weight evidence via the honesty
ladder as usual. Hybrid machines (native cycle data + CT clamp energy) declare
`data_source: hybrid`.

## 7. Conformance Vectors

The profile ships vectors covering:

- **Valid** - a full shift run (`run_type: shift`) with cycles, stops, and an
  energy interval; a `cycle_group` run bounded by `program_change`; a
  `needle_break` mid-run followed by `stop`/`start` with `reason`; a
  retrofit-only stream (cycle events + energy, no native-only events).
- **Invalid** - unknown `machine_class`; `press_cycle` with wrong-typed
  `temp_c`; `machine_fault` missing `code`; an event type not in core or this
  profile; a `phases[]` entry (this profile defines none, so any phase name
  is non-conformant).

## 8. Local-Language Glossary (Bangla first, per PROFILE-SPEC section 4)

| Identifier | বাংলা |
|---|---|
| `needle_break` | সুই ভাঙা |
| `thread_break` | সুতা ছেঁড়া |
| `bobbin_change` | ববিন বদল |
| `lockstitch` | লকস্টিচ (প্লেন মেশিন) |
| `overlock` | ওভারলক |
| `cycle_complete` | এক সাইকেল সম্পন্ন |

*(Expanded with the working group; Vietnamese and Hindi columns welcome.)*

## 9. Open Questions for the RFC

1. Should `cutting` be its own profile (cutting-room machines differ
   substantially from sewing machines)? Current position: keep it here until
   a cutting-room working group exists - moving it later is a major bump.
2. `stitch_count_update` cadence guidance - per-cycle vs periodic.
3. Whether `press_cycle` belongs here or in a future shared finishing
   vocabulary with `textile-dyeing`'s dryers (profile-inheritance question,
   architecture doc section 9).
