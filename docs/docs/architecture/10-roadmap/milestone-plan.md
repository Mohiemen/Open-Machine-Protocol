# Milestone Plan - The Living OMP Roadmap

| | |
|---|---|
| **Status** | Living document |
| **Location** | docs/architecture/10-roadmap/milestone-plan.md |
| **Last updated** | 2026-08-06 |
| **Rule** | This file MUST be updated in the same PR as any change that completes, adds, reorders, or invalidates a roadmap item. A milestone is not "achieved" until it is checked off here with a date. Stale roadmaps are bugs - file them like bugs. |

This is the single place where the project's plans and their real status meet.
Detailed rationale lives in the architecture docs; this file tracks *what* and
*when*, honestly. Every checked item carries its completion date. Items are
never silently deleted - superseded items are struck through with a note.

---

## Current Phase: Pre-v0.1 - Awaiting Hardware Validation

The spec is drafted in prose with normative JSON Schemas and executable
conformance vectors behind it, and the reference implementation runs: gateway
(validation, buffering, Ed25519 signing, exporters), `omp-validate` /
`omp-simulate` / `omp-sniff`, three adapters, and a reference consumer, all
under CI.

What separates this from v0.1 is **validation on real machines**, not more
code. Every remaining M2 sub-item and all of M3 needs physical hardware: an
ESP32 with a CT clamp, a Modbus PLC, a sewing machine, and a factory willing
to host a soak. The BDFL bootstrap phase (GOVERNANCE.md 4.5) remains in
effect until spec v1.0 or 5 core maintainers from 3 organizations.

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
- [ ] Independent conduct contact appointed (MAINTAINERS.md bootstrap note) - [#12](https://github.com/Mohiemen/Open-Machine-Protocol/issues/12)

### M1 - Normative spec artifacts

The prose spec declares JSON artifacts normative; until these exist the spec
cannot be conformance-tested.

- [x] JSON Schemas for envelope + 5 core schemas (spec/schemas/core/) *(2026-07-23)*
- [x] Conformance vectors, valid and invalid (spec/conformance/) - 22 core vectors, checksums computed via RFC 8785, all executing green *(2026-07-23)*
- [x] Consumer conformance vectors (spec/conformance/consumer/) - 8 executable suites (input.ndjson + implementation-agnostic expected.json), reference consumer passes all *(2026-08-06; the partial from 2026-07-23 is now complete)*
- [x] generic profile package (manifest, taxonomy, vocabulary) *(2026-07-23)*
- [x] textile-sewing and textile-dyeing profile packages with vectors *(2026-07-23)*
- [x] Profile authoring template (spec/profiles/_template/) *(2026-07-23)*

### M2 - v0.1 implementation (per architecture doc section 8)

- [x] Gateway runtime core - registry validation, engine (validate-before-buffer, dead letters, seq persistence), SQLite WAL buffer with exporter cursors, MQTT + stdout exporters, adapter API per the interface doc, `run-once` dev loop *(2026-07-23)*; Ed25519 signing + key management, `run` daemon, `install-service`/`show-identity`/`status`/`dead-letters` *(2026-07-23; REST/OPC UA/CSV exporters - CSV [#4](https://github.com/Mohiemen/Open-Machine-Protocol/issues/4), hot-reload [#10](https://github.com/Mohiemen/Open-Machine-Protocol/issues/10) remain)*; retention pruning with cursor safety, adapter restart policy, and probe timeouts *(2026-08-06)*
- [x] omp-validate CLI (profile-aware) - passes all conformance vectors, wired as pytest + CI *(2026-07-23)*
- [x] omp-simulate with generic, textile-sewing, textile-dyeing scenarios - chaos mode, MQTT export, seeded reproducibility *(2026-07-23)*
- [x] omp-sniff capture tool - serial + stdin capture, annotations, decode view *(2026-07-23; pcap mode still open - [#3](https://github.com/Mohiemen/Open-Machine-Protocol/issues/3))*
- [x] generic-modbus adapter with YAML register mapping - self-contained read-only TCP/RTU framing, on_increment/on_change/stats modes, injected-transport CI path *(2026-07-23; real-hardware soak pending)*
- [x] generic-serial adapter with line profiles and replay mode *(2026-07-23; real-hardware soak pending)*
- [~] retrofit-esp32 CT clamp firmware + hardware docs - **draft only** *(2026-07-23)*: firmware source, BOM/wiring, flashing and provisioning docs written to the retrofit guide's spec, plus the gateway-side `retrofit-esp32` adapter (replay-tested, 3 tests). The firmware itself was **never compiled or run** (no ESP32 toolchain available to its author) - it is a starting point, not a deliverable. Hardware validation tracked below - [#2](https://github.com/Mohiemen/Open-Machine-Protocol/issues/2).
- [x] Grafana example dashboards (examples/grafana-dashboards/) - compose stack (Mosquitto + Grafana + MQTT datasource) with provisioned Sewing Line Overview; config-validated, visual verification community-wanted, [#6](https://github.com/Mohiemen/Open-Machine-Protocol/issues/6) *(2026-07-23)*
- [x] Platform ingest reference consumer (examples/platform-ingest-reference/) - six-stage pipeline, integrity alarms, gap tracking, SQLite *(2026-07-23)*

### M3 - v0.1 release gate

Per README Status and vision doc section 7:

- [ ] Published spec with conformance vectors
- [ ] Working gateway + three adapters (generic-modbus, generic-serial, retrofit-esp32)
- [ ] One retrofit design validated on real hardware - first steps: compile the draft firmware, fix what breaks, verify the ADC/RMS calibration against a reference meter, then a week of soak. **The single highest-value contribution available right now** - [#2](https://github.com/Mohiemen/Open-Machine-Protocol/issues/2).
- [ ] Two end-to-end reference deployments - one real sewing machine, one Modbus PLC, both streaming signed conformant data to Grafana and one platform ingest example

---

## Post-v0.1 Horizon

### v0.2 (planned)

- [ ] `machining` profile (with MTConnect vocabulary mapping)
- [ ] `plastics` profile
- [ ] opcua-client adapter
- [x] `omp-validate --audit` (DPP evidence bundle verification, one command) - all five checks from DPP guide s4, records_hash, and the s3 citation block; unevaluable checks report null, never true *(2026-08-06)*
- [ ] First vendor adapters (candidates: juki-janets, sedo-treepoint, setex-secom, fanuc-focas, siemens-s7)

### v0.3 (planned)

- [ ] `packaging` and `utilities` profiles
- [ ] Sparkplug-compatible MQTT topic mapping (positioning doc 3.3)
- [ ] Bulk retrofit provisioning at fleet scale

### Open questions feeding future RFCs (architecture doc section 9, spec section 10)

- [~] Pin the signature input encoding - **[RFC 0001](../../../rfcs/0001-signature-input-encoding.md) drafted** *(2026-07-23)*, awaiting its 14-day comment window and a decision. Spec section 2 says `gateway_id || machine_id || seq || checksum` without defining the concatenation; the RFC pins LF-joined UTF-8 (what the reference implementation already does) and specifies the conformance vectors that land on acceptance. The normative spec is deliberately unchanged until then - process before convenience.
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
   Use `- [~]` for work that exists but is not validated (drafts, untested
   firmware); a `[~]` never counts toward a milestone being met.
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
| 2026-07-23 | M2 Phase 3: Ed25519 signing shipped end to end - on-device keypair (0600, never leaves), engine signs when enabled, omp-validate --pubkey verifies; sig-input encoding pinned in the reference implementation and flagged for a clarification RFC. Gateway service CLI: install-service, show-identity, run daemon (registry -> adapters -> signed envelopes -> exporters, machine announcement on startup), status, dead-letters. 76 tests green. Remaining in M2: ESP32 firmware, Grafana dashboards. |
| 2026-07-23 | Grafana dashboard stack added (compose + MQTT datasource provisioning + Sewing Line Overview); compose config and dashboard JSON validated, live visual check marked community-verify (no Docker daemon in CI). M2 now 8/9 - the sole remaining item, ESP32 retrofit firmware, is hardware-gated, as is the whole M3 release gate. |
| 2026-07-23 | Fixed a stale-roadmap bug: the phase header still claimed the repo was documentation-only with no implementation code, which stopped being true three commits earlier. Rewritten to state the real blocker - hardware validation, not more code. Also opened RFC 0001 (signature input encoding), the first RFC in the project's history, addressing the one open item that actively blocks a second implementation. |
| 2026-08-06 | Track C (partial): retention pruning that can never outrun delivery - it prunes only past the SLOWEST configured exporter's cursor, so a stalled exporter fills the disk (loud) rather than losing evidence (silent); a removed exporter's stale cursor cannot pin the buffer forever; every prune is logged and shown in `status`. Plus the adapter restart policy from API s6 (crash isolation, exponential backoff, machine marked failed after --max-crashes) and probe timeouts, so one hung serial port cannot stall floor startup. CSV exporter deliberately left for [#4](https://github.com/Mohiemen/Open-Machine-Protocol/issues/4) as a good-first-issue. 110 tests green. |
| 2026-08-06 | Track B: `omp-validate --audit` implements the five DPP checks (completeness, integrity, authenticity, consistency, conformance) and emits the citation block; 8 executable consumer conformance suites close M1's partial item. Two real bugs found by building them: the reference consumer rejected unknown event types from newer profile minors (violating spec s9 and the guide's own 'hard-coding profiles' warning), and omp-simulate reused run_ids across invocations against spec 7.3's uniqueness SHOULD. 102 tests green. |
| 2026-08-06 | PR #1 merged - the foundation is on main. Contributor on-ramp built: PR and issue templates (protocol capture, deployment report, adapter request, bug, translation), and 11 seeded issues so the good-first-issue links in README/CONTRIBUTING finally resolve. Open roadmap items are now cross-referenced to their tracking issues. |
| 2026-07-23 | Retrofit path drafted: esp32-ct-clamp firmware (provisioning AP, RMS sensing, node JSON over MQTT, offline ring buffer), BOM/wiring, FLASHING and PROVISIONING docs, and the gateway-side retrofit-esp32 adapter (node JSON -> energy/start/stop/maintenance_flag, replay-tested, 3 tests; 79 green overall). **The firmware was never compiled or run** - toolchain fetch failed in the authoring environment - so item 9 is marked `[~]` draft, not complete. Every M2 item is now either done or explicitly draft/hardware-gated; the project's remaining work is validation on real machines. |
