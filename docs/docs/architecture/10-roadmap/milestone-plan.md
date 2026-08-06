# Milestone Plan - The Living OMP Roadmap

| | |
|---|---|
| **Status** | Living document |
| **Location** | docs/architecture/10-roadmap/milestone-plan.md |
| **Last updated** | 2026-07-23 |
| **Rule** | This file MUST be updated in the same PR as any change that completes, adds, reorders, or invalidates a roadmap item. A milestone is not "achieved" until it is checked off here with a date. Stale roadmaps are bugs - file them like bugs. |

This is the single place where the project's plans and their real status meet.
Detailed rationale lives in the architecture docs; this file tracks *what* and
*when*, honestly. Every checked item carries its completion date. Items are
never silently deleted - superseded items are struck through with a note.

---

## Current Phase: Pre-v0.1 - Specification and Documentation

The repository is documentation-only today. The spec is drafted in prose; no
implementation code exists yet. The BDFL bootstrap phase (GOVERNANCE.md 4.5)
is in effect until spec v1.0 or 5 core maintainers from 3 organizations.

### M0 - Documentation foundation

- [x] Vision, positioning, stakeholder, and glossary docs published *(2026-07-23)*
- [x] Governance with constitutional principles published *(2026-07-23)*
- [x] Core schema specification v0.1 draft (prose) *(2026-07-23)*
- [x] Profile specification v0.1 draft with textile-dyeing worked example *(2026-07-23)*
- [x] Adapter Plugin API v0.1 draft *(2026-07-23)*
- [x] Getting-started, guides, integrations, security, community docs *(2026-07-23)*
- [x] Documentation consistency review (docs/REVIEW.md) *(2026-07-23)*
- [x] Resolve REVIEW.md section 1 conflicts (checksum format, telemetry fields, field naming, README overclaims) *(2026-07-23)*
- [x] MAINTAINERS.md with conduct and security contacts (bootstrap version; independent conduct contact still open) *(2026-07-23)*
- [x] Writing a Profile guide (docs/guides/writing-a-profile.md) *(2026-07-23)*
- [x] Security architecture / threat model doc (05-crosscutting) *(2026-07-23)*
- [x] textile-sewing profile documented (classes, events, phases) - Draft pending RFC/working group *(2026-07-23)*
- [x] Reference section scaffold (docs/reference/) - actual pages land with M2 *(2026-07-23)*
- [x] Translations scaffold (docs/translations/) *(2026-07-23)* - Bangla quickstart itself still open
- [x] rfcs/ directory with 0000-template.md; ADR directory (06-decisions/) *(2026-07-23)*
- [x] Bangla quickstart translation *(2026-07-23)*
- [ ] Independent conduct contact appointed (MAINTAINERS.md bootstrap note)

### M1 - Normative spec artifacts

The prose spec declares JSON artifacts normative; until these exist the spec
cannot be conformance-tested.

- [x] JSON Schemas for envelope + 5 core schemas (spec/schemas/core/) *(2026-07-23)*
- [x] Conformance vectors, valid and invalid (spec/conformance/) - 22 core vectors, checksums computed via RFC 8785, all executing green *(2026-07-23)*
- [x] Consumer conformance vectors (spec/conformance/consumer/) - cases defined; executable NDJSON suites land with the M2 reference consumer *(2026-07-23, partial)*
- [x] generic profile package (manifest, taxonomy, vocabulary) *(2026-07-23)*
- [x] textile-sewing and textile-dyeing profile packages with vectors *(2026-07-23)*
- [x] Profile authoring template (spec/profiles/_template/) *(2026-07-23)*

### M2 - v0.1 implementation (per architecture doc section 8)

- [x] Gateway runtime core - registry validation, engine (validate-before-buffer, dead letters, seq persistence), SQLite WAL buffer with exporter cursors, MQTT + stdout exporters, adapter API per the interface doc, `run-once` dev loop *(2026-07-23; service management, signing, and production adapter host remain - Phase 2)*
- [x] omp-validate CLI (profile-aware) - passes all conformance vectors, wired as pytest + CI *(2026-07-23)*
- [x] omp-simulate with generic, textile-sewing, textile-dyeing scenarios - chaos mode, MQTT export, seeded reproducibility *(2026-07-23)*
- [x] omp-sniff capture tool - serial + stdin capture, annotations, decode view *(2026-07-23; pcap mode still open)*
- [x] generic-modbus adapter with YAML register mapping - self-contained read-only TCP/RTU framing, on_increment/on_change/stats modes, injected-transport CI path *(2026-07-23; real-hardware soak pending)*
- [x] generic-serial adapter with line profiles and replay mode *(2026-07-23; real-hardware soak pending)*
- [ ] retrofit-esp32 CT clamp firmware + hardware docs
- [ ] Grafana example dashboards (examples/grafana-dashboards/)
- [x] Platform ingest reference consumer (examples/platform-ingest-reference/) - six-stage pipeline, integrity alarms, gap tracking, SQLite *(2026-07-23)*

### M3 - v0.1 release gate

Per README Status and vision doc section 7:

- [ ] Published spec with conformance vectors
- [ ] Working gateway + three adapters (generic-modbus, generic-serial, retrofit-esp32)
- [ ] One retrofit design validated on real hardware
- [ ] Two end-to-end reference deployments - one real sewing machine, one Modbus PLC, both streaming signed conformant data to Grafana and one platform ingest example

---

## Post-v0.1 Horizon

### v0.2 (planned)

- [ ] `machining` profile (with MTConnect vocabulary mapping)
- [ ] `plastics` profile
- [ ] opcua-client adapter
- [ ] `omp-validate --audit` (DPP evidence bundle verification, one command)
- [ ] First vendor adapters (candidates: juki-janets, sedo-treepoint, setex-secom, fanuc-focas, siemens-s7)

### v0.3 (planned)

- [ ] `packaging` and `utilities` profiles
- [ ] Sparkplug-compatible MQTT topic mapping (positioning doc 3.3)
- [ ] Bulk retrofit provisioning at fleet scale

### Open questions feeding future RFCs (architecture doc section 9, spec section 10)

- [ ] Profile inheritance (shared `wet-processing` base?)
- [ ] Operator identity - core, profile, or extension
- [ ] Time sync strategy for gateways without reliable NTP
- [ ] Quality/inspection results schema
- [ ] OPC UA companion spec / MTConnect formal alignment
- [ ] Go rewrite of gateway core once adapter API stabilizes
- [ ] Anchoring daily records_hash digests to a transparency log (DPP guide 6.5)

### Ecosystem milestones (vision doc section 7)

- [ ] Year 1 - 10+ community adapters; 3+ profiles in production; first factory running 50+ machines; first DPP citing OMP envelopes
- [ ] Governance - BDFL phase ends (spec v1.0 or 5 core maintainers / 3 orgs)
- [ ] Year 3 - OMP conformance appears in procurement requirements; first vendor ships OMP-native output

---

## How to Update This File

1. **Completing an item** - check it off with the date: `- [x] ... *(YYYY-MM-DD)*`.
2. **Adding work** - add it under the right milestone; if it changes scope
   meaningfully, note why in the changelog below.
3. **Dropping or superseding** - strike through (`~~item~~`) with a one-line
   reason and date; never delete.
4. **Always** bump the `Last updated` field and append a changelog line.
5. Spec-semantic items still need their RFC - this file tracks status, it does
   not replace process.

## Roadmap Changelog

| Date | Change |
|---|---|
| 2026-07-23 | Roadmap created; consolidated from README Status, architecture doc sections 8-9, vision doc section 7, and REVIEW.md gap list. M0 documentation items marked complete. |
| 2026-07-23 | REVIEW.md fix pass: all section-1 conflicts resolved; broken links repaired; MAINTAINERS.md, writing-a-profile guide, RFC template, ADR dir, translations and reference scaffolds created. Split out Bangla quickstart and independent conduct contact as their own items. |
| 2026-07-23 | M0 near-complete: security architecture/threat model doc authored (05-crosscutting); textile-sewing profile documented (Draft pending RFC); Bangla quickstart translated. Sole remaining M0 item: independent conduct contact (human appointment). |
| 2026-07-23 | M1 complete: 6 core JSON Schemas (draft 2020-12), core conformance vectors (9 valid / 13 invalid, RFC 8785 checksums via gen_vectors.py), machine-readable profile packages (generic, textile-dyeing, textile-sewing) each with vectors, profile template, consumer cases. All schemas metaschema-valid; all 36 vectors execute green. Consumer NDJSON suites deferred to M2 (need the reference consumer). |
| 2026-07-23 | M2 Phase 1 - the quickstart is real: omp-tools (omp-validate, omp-simulate) and omp-gateway (adapter API, engine, WAL store, MQTT/stdout exporters, run-once) shipped at repo root. 57 tests green including all 36 conformance vectors; documented quickstart pipeline verified end to end for all three profiles; GitHub Actions CI added (ruff + pytest + pipeline smoke). Phase 2 items: omp-sniff, adapters, firmware, dashboards, reference consumer, service management. |
| 2026-07-23 | M2 Phase 2: generic-serial (line profiles, stats aggregation, replay mode) and generic-modbus (YAML register maps, read-only-by-construction TCP/RTU framing, injected transport) adapters; omp-sniff (serial/stdin capture with annotations, decode view); platform-ingest-reference consumer (all six guide stages, integrity alarms, gap reporting). 71 tests green. Still open in M2: ESP32 firmware, Grafana dashboards, gateway service management, omp-sniff pcap. |
