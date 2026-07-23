# Glossary

| | |
|---|---|
| **Status** | Draft |
| **Owner** | M A Mohiemen Tanim |
| **Last updated** | July 2026 |
| **Location** | docs/architecture/00-overview/glossary.md |

---

Terms are used consistently across the specification, code, and documentation. When a term here conflicts with casual usage elsewhere in the repo, this document wins and the other text should be fixed.

## Core Terms

**Adapter**
A plugin that speaks one machine family's native protocol (or reads one retrofit sensor type) and emits OMP envelopes. Adapters implement the plugin contract (`probe`, `start`, `stop`, `health`) and never export data themselves - that is the gateway's job. Organized by protocol family (e.g. `generic-modbus`), not by industry.

**Anchor factory**
One of the first factories running OMP at meaningful scale (50+ machines), receiving direct support in exchange for case studies, hard bugs, and published results.

**Conformance vectors**
Published test payloads (valid and deliberately invalid) that adapters and consumer implementations are validated against. Passing conformance is a merge requirement for adapters.

**Consumer / Platform**
Any system that ingests OMP data - factory OS (e.g. Intelactory), MES, ERP, CMMS, dashboards, DPP generators. Consumers deduplicate on (`gateway_id`, `machine_id`, `seq`).

**Core (schemas)**
The five industry-neutral schemas - `machine`, `event`, `process_run`, `energy`, `telemetry` - plus the envelope. The core contains no industry-specific and no vendor-specific fields, ever.

**Dead letter**
A message that failed schema validation at the gateway. Written to a local dead-letter file for inspection, never silently dropped and never exported as valid data.

**Domain Profile (or just Profile)**
A small versioned package that specializes the core for one industry or machine family. Defines a machine class taxonomy, an event vocabulary extending the core set, process phase semantics, recommended telemetry channels, and its own conformance vectors. Examples - `textile-sewing`, `textile-dyeing`, `machining`. The `generic` profile is the fallback that lets any machine stream core events with no profile-specific semantics.

**Envelope**
The common wrapper around every OMP message, carrying `omp_version`, `profile`, `gateway_id`, `machine_id`, `seq`, `ts`, `schema`, `body`, and `checksum` (optionally a signature). The envelope, not the body, is what makes OMP data verifiable.

**Event**
A discrete occurrence emitted by a machine or inferred by an adapter - `cycle_complete`, `stop`, `error`, `needle_break`, `tool_change`. Core event types are universal; profiles add domain vocabulary.

**Exporter**
A gateway component that delivers buffered envelopes to consumers over one transport - MQTT, REST, OPC UA, or CSV. Each exporter keeps an independent cursor into the buffer, giving at-least-once delivery per destination.

**Gateway**
The edge runtime, typically one Raspberry Pi class device per floor. Hosts adapters, validates messages against core and profile schemas, buffers to a local append-only log, signs envelopes, and fans out to exporters. Identified by a unique `gateway_id` and a per-install keypair.

**Machine class**
A typed category within a profile's taxonomy, e.g. `lockstitch`, `overlock`, `jet_dyeing`, `cnc_mill_3axis`. Declared in `machine.json`.

**Machine registry**
The gateway's YAML configuration declaring each connected machine, its adapter, connection parameters, and profile.

**OMP (Open Machine Protocol)**
The project as a whole - specification, gateway implementation, adapter and profile library, retrofit designs, and tooling.

**Process run**
A bounded unit of work recorded in `process_run.json` - a dye batch, a CNC job, a molding cycle group, a shift. Contains phases, timestamps, outcome, and quantities. The genealogy unit that DPP-class traceability builds on.

**Retrofit (node / kit)**
Open hardware (typically ESP32-based) attached to a machine with no digital output - CT clamp for energy, vibration sensor, optical cycle counter. A retrofit node is a special adapter class that reports to the gateway over local WiFi or ESP-NOW using the same envelope format.

**Seq (sequence number)**
A per-machine, monotonically increasing counter assigned by the gateway. Gaps in `seq` are detectable by any consumer, which is what makes data completeness auditable.

**Telemetry**
Continuous sensor streams (temperature, vibration, current) carried in `telemetry.json`, either as raw sampled values or bandwidth-saving statistics (min/max/avg per interval).

## Verifiability Terms

**Checksum**
SHA-256 hash over the envelope body, computed at the gateway before buffering. Detects post-emission tampering.

**Gateway keypair**
An Ed25519 keypair generated at gateway installation. The public key identifies the gateway to consumers; the private key never leaves the device.

**Machine-attested**
Data whose lineage can be verified back to a specific gateway and sequence range via checksums and signatures, as opposed to self-declared data entered by a person. OMP's evidence claims are always scoped honestly - see the DPP Evidence Chain guide for exactly what is and is not proven.

**Signature**
Optional Ed25519 signature over the envelope for high-assurance deployments. Distinct from the always-present checksum.

## Ecosystem and Governance Terms

**ADR (Architecture Decision Record)**
A short immutable document recording one significant decision, its context, and its consequences. Stored in `docs/architecture/06-decisions/`. ADRs are superseded, never edited.

**Extension block (`x-*`)**
A namespaced object inside a message body carrying platform-specific or vendor-specific fields, e.g. `x-intelactory`. Core validators ignore extension blocks. Extensions never appear in core or profile schemas.

**Maintainer**
A person with merge rights over a defined area (core, a profile, an adapter). Adapters require a named maintainer to be accepted.

**RFC (Request for Comments)**
The public proposal process for changes to the specification or to profiles. Implementation details do not require RFCs; spec semantics do.

**Semver (semantic versioning)**
Version discipline applied independently to the core spec, each profile, and each adapter. Breaking changes bump major; additive changes bump minor. Consumers must accept any same-major version.

**Vendor-verified (adapter tier)**
An adapter co-maintained with the machine vendor and tested against vendor documentation, badged accordingly. Vendor participation grants co-maintenance, never ownership - community fork rights are absolute.

## Deployment Terms

**At-least-once delivery**
The export guarantee - every envelope reaches each configured destination one or more times. Duplicates are possible and expected; consumers deduplicate on (`gateway_id`, `machine_id`, `seq`).

**Buffer (append-only log)**
The gateway's local SQLite WAL store holding validated envelopes until all exporters have delivered them, surviving power loss. Default retention 30 days or a disk threshold.

**OT / IT segmentation**
The standard factory network split - Operational Technology (machines, controllers, the gateway) isolated from Information Technology (office, internet). The gateway sits in OT and exports through a single controlled egress point.

**Register map**
A YAML file describing the Modbus register layout of a specific device, used by `generic-modbus` so new devices can be supported without writing code.

## Abbreviations

| | |
|---|---|
| CMMS | Computerized Maintenance Management System |
| CT clamp | Current Transformer clamp (non-invasive current sensing) |
| DPP | Digital Product Passport (EU ESPR instrument) |
| ESPR | Ecodesign for Sustainable Products Regulation (EU) |
| MES | Manufacturing Execution System |
| MQTT | Message Queuing Telemetry Transport |
| NDJSON | Newline-Delimited JSON |
| OEE | Overall Equipment Effectiveness |
| OPC UA | Open Platform Communications Unified Architecture |
| PLC | Programmable Logic Controller |
| SCADA | Supervisory Control and Data Acquisition |
| WAL | Write-Ahead Log (SQLite journaling mode) |
