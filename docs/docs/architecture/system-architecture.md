# Open Machine Protocol (OMP) - Architecture Document v0.2

**Status** - Draft
**Date** - July 2026
**Change from v0.1** - Generalized from textile-only to all industrial machinery. Domain knowledge moved out of the core into Domain Profiles.
**Audience** - Contributors, integrators (Intelactory and similar platforms), factory deployment engineers across industries

---

## 1. Purpose and Scope

OMP is an open-source driver layer and data standard for industrial machinery of any kind - sewing lines, dyeing machines, CNC mills, injection molders, packaging lines, compressors, boilers, conveyors. It converts heterogeneous machine signals (proprietary protocols, PLC tags, retrofit sensors) into a single, versioned, vendor-neutral event schema that any upstream platform can consume.

Positioning in one line - **what OBD-II did for cars, OMP does for industrial machines.**

**In scope for v0.1 release**

- Domain-neutral core schema (machine identity, events, process runs, energy, telemetry)
- Domain Profile mechanism, shipping with two reference profiles (textile-sewing, textile-dyeing)
- Edge gateway runtime with plugin adapter model
- Reference adapters - generic-serial (RS232/RS485) and generic-modbus (RTU/TCP, covers a huge share of industrial equipment)
- Reference retrofit design (ESP32 + CT clamp)
- MQTT exporter and schema validation CLI

**Out of scope**

- Machine control or write-back commands (read-only by design)
- Cloud services, dashboards, analytics (upstream platform responsibility)

---

## 2. Design Principles

1. **Domain-neutral core, domain-rich profiles.** The core schemas know nothing about stitches or dye baths. Industry semantics live in Domain Profiles, so a CNC shop and a dye house run the same gateway, same envelope, same tooling.
2. **Spec first, code second.** The schemas are the product. Any implementation in any language that emits conformant data is a valid OMP source.
3. **Read-only at the edge.** OMP observes machines, never commands them. This removes an entire class of safety and liability risk.
4. **Vendor neutrality.** No platform-specific fields in core or profiles. Extensions live in namespaced blocks (e.g. `x-intelactory`).
5. **Offline first.** The gateway buffers locally and replays on reconnect with no data loss.
6. **Verifiable at source.** Every event carries a monotonic sequence number, gateway identity, and checksum, so downstream consumers (DPP generators, auditors) can prove data lineage.
7. **Low-resource friendly.** Runs on Raspberry Pi class hardware in hot, dusty, electrically noisy environments.

---

## 3. System Overview

```
┌────────────────────────────────────────────────────────┐
│ LAYER 4 - CONSUMER PLATFORMS                           │
│ Intelactory, ERP, MES, CMMS, BI, DPP generators        │
└───────────────▲────────────────────────────────────────┘
                │ MQTT / REST / OPC UA / CSV
┌───────────────┴────────────────────────────────────────┐
│ LAYER 3 - OMP GATEWAY (edge runtime)                   │
│ Adapter host · Profile-aware validation · Buffer/      │
│ replay · Event signing · Machine registry · Exporters  │
└───────────────▲────────────────────────────────────────┘
                │ Adapter plugin API
┌───────────────┴────────────────────────────────────────┐
│ LAYER 2 - ADAPTERS                                     │
│ generic-modbus · generic-serial · opcua-client ·       │
│ juki-janets · sedo-treepoint · fanuc-focas ·           │
│ siemens-s7 · retrofit-esp32 · (community adapters)     │
└───────────────▲────────────────────────────────────────┘
                │ Serial / Fieldbus / Ethernet / GPIO
┌───────────────┴────────────────────────────────────────┐
│ LAYER 1 - MACHINES AND SENSORS                         │
│ PLCs · CNC controllers · Process controllers ·         │
│ Legacy serial equipment · Retrofit sensor kits         │
└────────────────────────────────────────────────────────┘
```

---

## 4. Core Architecture

### 4.1 Core Schemas (`spec/schemas/core/`)

JSON Schema draft 2020-12, semantically versioned. Every payload carries `omp_version` and `profile`.

| Schema | Purpose | Key fields |
|---|---|---|
| `machine.json` | Identity and capability declaration | `machine_id`, `machine_class` (from profile taxonomy), `make`, `model`, `profile`, `capabilities[]`, `location` (site/area/line/station) |
| `event.json` | Discrete occurrences | `event_type` (core set + profile vocabulary), `ts`, `seq`, `severity`, `payload` |
| `process_run.json` | Bounded unit of work | `run_id`, `run_type` (batch, job, cycle_group, shift), `program_ref`, `phases[]`, `start_ts`, `end_ts`, `outcome`, `quantities[]` |
| `energy.json` | Utility consumption | `metric` (kwh, water_l, steam_kg, air_m3, gas_m3), `value`, `interval`, `source` (native/ct_clamp/submeter/estimated) |
| `telemetry.json` | Continuous sensor streams | `channel`, `unit` (UCUM), `mode` (samples/stats), `samples[]` of `{t, v}` pairs or `stats` (min/max/avg/count) |

**Core event types (universal)** - `run_start`, `run_end`, `cycle_complete`, `stop`, `start`, `error`, `alarm`, `maintenance_flag`, `state_change`. Everything more specific comes from a profile.

**Envelope** - unchanged, and now carries the profile reference:

```json
{
  "omp_version": "0.1.0",
  "profile": "textile-sewing/0.1",
  "gateway_id": "gw-dhaka-f1-01",
  "machine_id": "f1-line3-m07",
  "seq": 48291,
  "ts": "2026-07-24T09:14:03.221Z",
  "schema": "event",
  "body": { },
  "checksum": "9f2a...c4"
}
```

### 4.2 Domain Profiles (`spec/profiles/`)

A profile is a small, versioned package that specializes the core for one industry or machine family. This is the key mechanism that keeps OMP universal without becoming vague.

**A profile defines**

1. A machine_class taxonomy (e.g. `lockstitch`, `overlock`, `jet_dyeing`, `cnc_mill_3axis`, `injection_molder`)
2. An event_type vocabulary extending the core set (e.g. `needle_break`, `tool_change`, `mold_open`, `dosing_complete`)
3. Phase semantics for `process_run` (e.g. dyeing - heat, hold, cool, rinse; molding - inject, pack, cool, eject)
4. Recommended telemetry channels and units
5. Conformance vectors for validation

**Planned profile roadmap**

| Profile | Ships | Covers |
|---|---|---|
| `textile-sewing` | v0.1 | Sewing, cutting, finishing machines |
| `textile-dyeing` | v0.1 | Jet/winch/pad dyeing, washing |
| `machining` | v0.2 | CNC mills, lathes, EDM |
| `plastics` | v0.2 | Injection molding, extrusion |
| `packaging` | v0.3 | Filling, sealing, labeling lines |
| `utilities` | v0.3 | Compressors, boilers, generators, chillers |
| `generic` | v0.1 | Fallback - core events only, any machine |

Profiles are community-authored via RFC, same governance as core. The `generic` profile guarantees that a machine with no profile yet can still stream conformant data from day one.

### 4.3 Adapters (`adapters/`)

Same plugin contract as before (`probe`, `start`, `stop`, `health`), now organized by protocol family rather than industry, because protocols cut across industries:

- **generic-modbus** - Modbus RTU/TCP. The single highest-leverage adapter, covers countless PLCs, meters, drives, and controllers across every industry. Ships with a mapping-file format so users describe register maps in YAML instead of writing code.
- **generic-serial** - profile-driven RS232/RS485 for legacy controllers.
- **opcua-client** - consumes existing OPC UA servers and re-emits as OMP (bridge for modern plants).
- **Vendor adapters** - juki-janets, brother-nexio, sedo-treepoint, setex-secom, fanuc-focas, siemens-s7, etc.
- **retrofit-esp32** - CT clamp, vibration, optical counter firmware for dumb machines in any industry.

An adapter declares which profiles it can emit. generic-modbus + a YAML register map + the `generic` profile means almost any industrial machine can join OMP without writing code.

### 4.4 Gateway, Exporters, Tooling

Unchanged from v0.1 architecture - registry, adapter lifecycle, validation against core + profile schemas, SQLite WAL buffering with replay, per-gateway signing, and fan-out to MQTT / REST / OPC UA / CSV exporters. Tools (`omp-validate`, `omp-simulate`, `omp-sniff`) become profile-aware, e.g. `omp-simulate --profile plastics` generates realistic injection molding data.

Topic convention gains the site dimension - `omp/{site}/{area}/{line}/{machine}/{schema}`.

---

## 5. Repo Structure (updated)

```
omp/
├── spec/
│   ├── schemas/core/            # machine, event, process_run, energy, telemetry
│   ├── profiles/
│   │   ├── generic/
│   │   ├── textile-sewing/
│   │   ├── textile-dyeing/
│   │   └── _template/           # profile authoring kit
│   └── conformance/
├── adapters/
│   ├── generic-modbus/
│   ├── generic-serial/
│   ├── opcua-client/
│   ├── juki-janets/  sedo-treepoint/  fanuc-focas/  siemens-s7/ ...
│   └── _template/
├── retrofit/
│   ├── esp32-ct-clamp/  esp32-vibration/  esp32-optical-counter/
├── gateway/
│   ├── core/  exporters/  config/
├── tools/
│   ├── omp-validate/  omp-simulate/  omp-sniff/
├── docs/
│   ├── getting-started.md  factory-deployment.md
│   ├── writing-a-profile.md  writing-an-adapter.md
│   └── translations/bn/
└── examples/
    ├── sewing-line-10-machines/
    ├── dye-house-batch-tracking/
    ├── modbus-generic-plc/
    └── grafana-dashboards/
```

---

## 6. Integration Architecture (Intelactory and Similar Platforms)

Unchanged pattern - MQTT subscription, dedup on (`gateway_id`, `machine_id`, `seq`), landing in the platform's own store. What generalization adds:

| OMP object | Platform concept |
|---|---|
| `machine.json` + profile | Asset registry with typed capabilities per industry |
| `event.json` | Production counts, OEE, downtime analysis |
| `process_run.json` | Batch/job genealogy feeding DPP or traceability |
| `energy.json` | Utility allocation per run/order across all machine types |
| Envelope (seq, checksum, signature) | Source-verification evidence for DPP claims |

The DPP evidence chain now works identically for a dyed batch, a molded component, or a machined part - claims reference envelope ID ranges, profile version, and gateway signature verification. One ingestion module, every industry the community ever writes a profile for.

Platform extensions remain namespaced (`x-intelactory`) and outside core and profiles.

---

## 7. Security, Deployment, Governance

Unchanged from v0.1 - read-only principle, TLS transport, per-gateway keypairs with optional Ed25519 signatures, OT/IT segmentation reference topology, semver on core and on each profile independently, RFC process for both spec and profile changes, adapter acceptance requiring conformance pass and a named maintainer.

Deployment references now include a generic discrete-manufacturing floor (Modbus PLCs + gateway) alongside the sewing floor and dye house references.

---

## 8. v0.1 Milestone Checklist (revised)

- [ ] Envelope + 5 core schemas + conformance vectors
- [ ] `generic`, `textile-sewing`, `textile-dyeing` profiles
- [ ] Gateway runtime with registry, buffer, MQTT exporter
- [ ] generic-modbus adapter with YAML register mapping
- [ ] generic-serial adapter with one documented machine profile
- [ ] ESP32 CT clamp firmware + hardware docs
- [ ] omp-validate CLI (profile-aware)
- [ ] Two end-to-end demos - a sewing machine and a Modbus PLC, both streaming to Grafana and one platform ingest example

## 9. Open Questions for v0.2+

1. Profile inheritance (can `textile-dyeing` extend a shared `wet-processing` base?)
2. Operator identity capture - core, profile, or extension?
3. Time sync for gateways without reliable NTP
4. Formal alignment with OPC UA companion specs and MTConnect (machining domain overlap)
5. Go rewrite of gateway core once adapter API stabilizes
