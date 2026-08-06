# Reference

| | |
|---|---|
| **Status** | Scaffold - pages land alongside the v0.1 implementation |
| **Location** | docs/reference/ |

Exact, look-it-up documentation. Explanatory material lives in
[getting-started](../getting-started/) and [guides](../guides/); normative
schema rules live in the [core spec](../../spec/omp-schema-v0.1.md).

## Planned pages

| Page | Covers | Status |
|---|---|---|
| `envelope.md` | Envelope fields, patterns, sequence and time semantics (non-normative summary of spec sections 2-5) | planned |
| `config.md` | Gateway config + machine registry (`registry.yaml`) full field reference | planned |
| `cli.md` | `omp-gateway`, `omp-validate`, `omp-simulate`, `omp-sniff` commands and flags | planned |
| `mqtt-topics.md` | Topic convention `omp/{site}/{area}/{line}/{machine}/{schema}`, QoS, subscription patterns | planned |
| `mapping-files.md` | `generic-modbus` register map and `generic-serial` line profile formats | planned |
| `exporters.md` | MQTT / REST / OPC UA / CSV exporter configuration | planned |

Until these exist, the interim sources are: envelope - core spec and the
normative JSON Schemas in `spec/schemas/core/`; registry and mapping examples -
[First Real Machine](../getting-started/first-real-machine.md); CLI behavior -
the guides that use each command; topics - [Platform
Ingestion](../integrations/platform-ingestion.md).
