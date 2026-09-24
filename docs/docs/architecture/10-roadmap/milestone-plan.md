# Milestone Plan - The Living OMP Roadmap

| | |
|---|---|
| **Status** | Living document |
| **Location** | docs/architecture/10-roadmap/milestone-plan.md |
| **Last updated** | 2026-09-24 |
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

- [x] Gateway runtime core - registry validation, engine (validate-before-buffer, dead letters, seq persistence), SQLite WAL buffer with exporter cursors, MQTT + stdout exporters, adapter API per the interface doc, `run-once` dev loop *(2026-07-23)*; Ed25519 signing + key management, `run` daemon, `install-service`/`show-identity`/`status`/`dead-letters` *(2026-07-23; REST/OPC UA/CSV exporters - CSV [#4](https://github.com/Mohiemen/Open-Machine-Protocol/issues/4), remain)*; retention pruning with cursor safety, adapter restart policy, probe timeouts, and registry hot-reload *(2026-08-06)*
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

---

## Unblocked Work Queue

Everything else on this roadmap waits on hardware, a maintainer decision, or
an industry practitioner. This section is the work that needs **none of
those** - it can start today - in the order it should be done, with the
reason for that order.

The whole queue exists because of one finding: a sweep of the docs against
the implementation (2026-08-06) found capabilities **documented as if they
already exist** but never built. Those are the same class of defect as the
broken good-first-issue links - a promise the repo does not keep - and they
outrank new features.

### The sequence

**All five are done** *(2026-09-24)*. What remains on this roadmap needs
hardware, a maintainer decision, or an industry practitioner - see the
sections after this one.

1. ~~**Adapter transport pool (`self.transport(...)`)**~~ - **done 2026-08-06**:
   `omp/core/transports.py` (TransportPool + SharedTransport), `self.transport()`
   and `release_transports()` on AdapterBase, generic-modbus using it for both
   RTU and TCP, one pool shared per daemon, and the API doc now carries the
   concrete contract instead of only naming the helper. The interleaving test
   has a negative control: the same workload without the pool interleaves 29 of
   30 transactions, with it 0. Originally promised by
   [Adapter Plugin API s4](../04-interfaces/adapter-plugin-api.md): "shared
   transports are managed via the gateway's transport pool so two instances
   can share one RS485 line safely". It does not exist, so today two machines
   on one multi-drop bus each open their own port and collide. **First
   because it is an API contract**: every adapter written before it lands is
   written without it, and multi-drop RS485 is the normal textile-floor
   topology, not an edge case. Testable with fake transports.

2. ~~**`omp-gateway tail`**~~ - **done 2026-08-06**: streams the buffer as
   NDJSON, follows by default, `--no-follow` / `--last N` / `--machine`.
   Read-only by construction - it never acks, because an observer that
   advanced an exporter cursor would let retention prune undelivered data.
   `omp-validate` now also summarises on Ctrl-C so the documented
   `tail | omp-validate` loop ends with a verdict. Originally used in
   [First Real Machine s6](../../getting-started/first-real-machine.md)
   (`omp-gateway tail | omp-validate`) as part of the documented
   first-machine loop. Smallest item here and immediately useful to anyone
   following the guide.

3. ~~**REST exporter**~~ - **done 2026-08-06**: batched NDJSON with gzip, acks
   only after a 2xx, transient failures leave the batch buffered, a 4xx stops
   rather than wedging the buffer behind data the endpoint will never accept,
   and plain HTTP to a non-loopback host is refused at construction per
   Hardening Guide s5 [Required]. Building it exposed that the daemon drained
   once per envelope, so a "batching" exporter posted one envelope per
   request - exports are now coalesced by a drain worker (`--drain-interval`).
   Originally from [Platform Ingestion s1](../../integrations/platform-ingestion.md)
   lists four transports; MQTT and stdout exist, CSV is reserved as a good
   first issue ([#4](https://github.com/Mohiemen/Open-Machine-Protocol/issues/4)),
   REST is unclaimed. Must return 200 only after a durable write, and must
   not ack past what the destination accepted. Verifiable against a local
   HTTP server in-process.

4. ~~**`omp-gateway audit-host`**~~ - **done 2026-09-22**: seven checks over
   a host tree (SSH policy including `sshd_config.d` drop-ins,
   unattended-upgrades, the unprivileged service user, serial device-group
   access, co-tenant detection, keypair mode, NTP sync), a stored baseline in
   the state dir, and drift reporting that fires on an evidence change even
   when the verdict holds - `AllowUsers ops` becoming `AllowUsers
   ops,contractor` is still a pass and still something the weekly rhythm
   should surface. Exit codes are shaped for cron: 0 clean, 1 drift only, 2 a
   Required check failing. **A check that cannot be evaluated reports UNKNOWN
   and never collapses into a pass** - the same discipline as `null`-not-`true`
   in the DPP audit tool, because the dangerous failure mode here is auditing
   a host where nothing is readable and getting a clean bill of health. Also
   wrote `docs/security/examples/99-omp-serial.rules`, which the guide
   referenced but the repo did not contain. Verified against this real
   container (correctly reports docker/postgres co-tenancy and a chmod 644
   keypair as drift), not only against fixtures. Originally from
   [Hardening Guide s3](../../security/hardening-guide.md): "runs these checks
   and reports drift; wire it into the weekly rhythm".

5. ~~**`omp-gateway verify-release`**~~ - **done 2026-09-24**: minisign
   verification, both the prehashed (`ED`) and legacy (`Ed`) formats, plus
   the trusted comment's own global signature - without that check an
   attacker keeps a valid file signature and rewrites the version string the
   operator actually reads. It **never fetches a key**: one that travels
   with the artifact proves only that a single party controlled both, which
   is exactly an attacker's position. A checksum file with no signature over
   it is reported as adding no provenance rather than as a pass. Exit 0 only
   when a signature was checked and passed; "cannot verify" is exit 1, so a
   rollout script cannot confuse the two. Tested against **vectors produced
   by the real minisign 0.11**, not by our own code - including the
   rewritten-comment vector that `minisign -V` rejects with "Comment
   signature verification failed", and which we reject for the same reason.
   Originally from [Hardening Guide s6](../../security/hardening-guide.md)
   **[Required]**.

   **Still maintainer-blocked, and the guide now says so**: no OMP release
   key exists. The verifier is complete, but s6 cannot be satisfied by any
   deployment until a key is generated, published through a channel
   independent of the artifacts, and pinned in the installed package
   (`omp/release-key.pub`).

### Reserved, not forgotten

These are unblocked but deliberately left for first-time contributors - the
project needs an on-ramp more than it needs the features, and taking them
would empty it:

| Item | Issue |
|---|---|
| `omp-sniff` pcap mode | [#3](https://github.com/Mohiemen/Open-Machine-Protocol/issues/3) |
| CSV exporter | [#4](https://github.com/Mohiemen/Open-Machine-Protocol/issues/4) |
| Grafana visual verification | [#6](https://github.com/Mohiemen/Open-Machine-Protocol/issues/6) |
| Bangla first-real-machine | [#7](https://github.com/Mohiemen/Open-Machine-Protocol/issues/7) |
| Modbus register maps | [#8](https://github.com/Mohiemen/Open-Machine-Protocol/issues/8) |

**The on-ramp works**: the CLI reference page (#5) was claimed and delivered
by an outside contributor ([PR #14](https://github.com/Mohiemen/Open-Machine-Protocol/pull/14),
merged 2026-09-15) - the project's first contribution from someone other than
the maintainer. Six reserved items became five without anyone here touching
it.

If no one claims one within a reasonable window, it stops being an on-ramp
and becomes a gap - take it then.

### Blocked, for contrast

Not in this queue and not startable: `omp-gateway retrofit-update` (needs
nodes), the OPC UA exporter and `opcua-client` adapter (need a server to
verify against - shipping either unverified would repeat the ESP32 mistake),
every M3 item (hardware), all remaining profiles (GOVERNANCE 6.2 requires 2+
industry practitioners each), and the open RFC questions (decisions, not
tasks).

### Not on the roadmap but ahead of all of it

**CI runs again, and it caught a real bug** *(resolved 2026-09-24)*. Workflow
runs resumed by 2026-09-15. They were **failing** - two `test_reload` cases
red on `main` for nine days, and nobody looked, which is the same failure as
not having CI at all. Root cause: this project's dev container sets
`PYTHONUNBUFFERED=1`; the GitHub runner and a real gateway do not. That
variable was hiding a missing `flush()` in the stdout exporter - it acked
envelopes that existed only in its own process buffer, so a kill or a power
cut lost data the cursor had already recorded as delivered. At-most-once
wearing at-least-once's name, on the exporter the quickstart uses. Fixed,
with a negative control, and `AGENTS.md` now documents the trap.

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
| 2026-08-06 | Queue item 3 done: REST exporter (batched NDJSON, gzip, ack-only-after-2xx, refuses plaintext HTTP off-loopback). Verified against a live HTTP server that writes to disk before returning 200. The end-to-end run exposed a real defect the unit tests could not: the daemon drained after every emit, so the batching exporter sent one envelope per request - exports are now coalesced by a drain worker, and `--drain-interval` genuinely trades latency for batch size. 140 tests green. |
| 2026-08-06 | Queue item 2 done: `omp-gateway tail` exists, so the loop first-real-machine s6 documents actually runs. It observes without acking - tailing must never let retention think data was delivered - and `omp-validate` now prints its summary on Ctrl-C instead of dying, which is what makes `tail | omp-validate` usable live. Testing the documented command found the first cut wrong: `--no-follow` started from 'now' and printed nothing. 125 tests green. |
| 2026-08-06 | Queue item 1 done: the adapter transport pool exists, so several machines on one RS485 pair (or one Modbus TCP gateway) share a link and their transactions serialize. The unit of exclusion is the whole request/response round trip, because splitting it is what makes unit 1 read unit 2's reply - a failure that shows up as random CRC errors on real hardware. Verified with a negative control, not just a passing test. 119 tests green. |
| 2026-09-24 | Extended the contributor's CLI reference ([cli.md](../../reference/cli.md)) to cover `tail`, `audit-host` and `verify-release`, which landed after it was written - including the exit-code tables, since both new commands are meant to be run from cron and the difference between "drift" and "Required failing" is the whole point. Merged `main` into the branch to pick it up. All relative doc links re-checked. |
| 2026-09-24 | Queue item 5: `omp-gateway verify-release`, and with it the Unblocked Work Queue is empty. minisign verification in both formats, including the global signature over the trusted comment - the check that stops a valid file signature being paired with a forged version string. It never fetches a key, and never reports a pass for a check it did not perform: no pinned key is exit 1, not silence. Tested against vectors generated by the real minisign 0.11 rather than by our own implementation, so the tests measure interoperability instead of self-consistency; secret keys were deleted and never committed. Hardening Guide s6 now states plainly that no release key exists yet, so the [Required] item cannot yet be satisfied by any deployment. 192 tests green. |
| 2026-09-24 | Fixed the CI failure that had been red on `main` since 2026-09-15, and it was not a test bug. The stdout exporter wrote without flushing, so `drain()` acked envelopes still sitting in the process buffer - a kill or a power cut lost data the cursor called delivered, and `omp-gateway run > floor.ndjson` looked dead for its first 8 KiB. It passed locally only because this dev container sets `PYTHONUNBUFFERED=1`, which CI and real gateways do not. Flush before ack, flush failures no longer ack, `test_reload` now strips the variable from the daemon's environment so it cannot be masked again, and `AGENTS.md` documents the trap. Negative control: reverting the flush fails all four tests. Verified against a real redirected daemon run. 167 tests green. |
| 2026-09-24 | First outside contribution merged: the CLI reference page ([#5](https://github.com/Mohiemen/Open-Machine-Protocol/issues/5), [PR #14](https://github.com/Mohiemen/Open-Machine-Protocol/pull/14)) by @slegarraga. Removed from the reserved table - the on-ramp did what it was for. |
| 2026-09-22 | Queue item 4: `omp-gateway audit-host` - the host-posture check Hardening Guide s3 promised. Seven checks, a baseline in the state dir, and drift reporting sensitive to evidence changes and not only verdict flips. Unknown never reads as pass, and the report says so in words. Added the `99-omp-serial.rules` example the guide pointed at but the repo lacked. 165 tests green; lint clean; driver `all` green. |
| 2026-08-06 | Added the Unblocked Work Queue after sweeping the docs against the implementation: four capabilities were documented as existing but never built (`tail`, `audit-host`, `verify-release`, the adapter transport pool). Sequenced them, recorded which unblocked items stay reserved for first-time contributors, and flagged that CI is currently not running - which outranks the whole queue. |
| 2026-08-06 | Registry hot-reload ([#10](https://github.com/Mohiemen/Open-Machine-Protocol/issues/10)): `omp-gateway reload` signals a running gateway over SIGHUP; the new registry is validated in full - including that every named adapter loads - BEFORE anything is touched, so an operator pulling a bad file from git gets a refusal and an unchanged floor rather than an outage. Machines whose config is byte-identical are left running, so their seq continuity is never broken. Verified end to end against a live daemon. 113 tests green. |
| 2026-08-06 | Track C (partial): retention pruning that can never outrun delivery - it prunes only past the SLOWEST configured exporter's cursor, so a stalled exporter fills the disk (loud) rather than losing evidence (silent); a removed exporter's stale cursor cannot pin the buffer forever; every prune is logged and shown in `status`. Plus the adapter restart policy from API s6 (crash isolation, exponential backoff, machine marked failed after --max-crashes) and probe timeouts, so one hung serial port cannot stall floor startup. CSV exporter deliberately left for [#4](https://github.com/Mohiemen/Open-Machine-Protocol/issues/4) as a good-first-issue. 110 tests green. |
| 2026-08-06 | Track B: `omp-validate --audit` implements the five DPP checks (completeness, integrity, authenticity, consistency, conformance) and emits the citation block; 8 executable consumer conformance suites close M1's partial item. Two real bugs found by building them: the reference consumer rejected unknown event types from newer profile minors (violating spec s9 and the guide's own 'hard-coding profiles' warning), and omp-simulate reused run_ids across invocations against spec 7.3's uniqueness SHOULD. 102 tests green. |
| 2026-08-06 | PR #1 merged - the foundation is on main. Contributor on-ramp built: PR and issue templates (protocol capture, deployment report, adapter request, bug, translation), and 11 seeded issues so the good-first-issue links in README/CONTRIBUTING finally resolve. Open roadmap items are now cross-referenced to their tracking issues. |
| 2026-07-23 | Retrofit path drafted: esp32-ct-clamp firmware (provisioning AP, RMS sensing, node JSON over MQTT, offline ring buffer), BOM/wiring, FLASHING and PROVISIONING docs, and the gateway-side retrofit-esp32 adapter (node JSON -> energy/start/stop/maintenance_flag, replay-tested, 3 tests; 79 green overall). **The firmware was never compiled or run** - toolchain fetch failed in the authoring environment - so item 9 is marked `[~]` draft, not complete. Every M2 item is now either done or explicitly draft/hardware-gated; the project's remaining work is validation on real machines. |
