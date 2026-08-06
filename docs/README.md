# Open Machine Protocol (OMP)

**What OBD-II did for cars, OMP does for industrial machines.**

OMP is an open-source driver layer and data standard that turns any industrial machine into a source of standardized, verifiable operational data. A 1998 lockstitch sewing machine, a Modbus PLC, a jet dyeing controller, a CNC mill - one envelope format, one gateway, one integration surface for every platform above it.

- 🔌 **Any machine** - protocol adapters for networked controllers, $15 ESP32 retrofit kits for machines with no digital output at all
- 📋 **One open schema** - domain-neutral core plus industry Domain Profiles (textile, machining, plastics, and growing)
- 🔒 **Read-only by design** - OMP observes machines, never commands them. Constitutional, not configurable.
- ✅ **Verifiable at source** - sequence numbers, checksums, and gateway signatures make every event auditable, strong enough to cite in a Digital Product Passport
- 📴 **Offline-first, Pi-class** - built for factories with unstable power, unreliable networks, and real budgets

**No cloud. No subscription. Your machines, your data.**

---

## Why OMP Exists

Most of the world's industrial machines are digitally mute. Every machine maker speaks its own protocol, legacy equipment has no digital output at all, and commercial IoT platforms are priced for the factories that need them least. Meanwhile, regulations like the EU Digital Product Passport increasingly demand evidence of how goods were made - and today that evidence is mostly self-declared spreadsheets.

OMP fills the gap no existing standard reaches - rich data semantics AND the legacy long tail. OPC UA and MTConnect serve modern, vendor-enabled equipment well, and OMP bridges to both. But nobody serves the 30-year-old machine running perfectly in a factory in Gazipur, Ho Chi Minh City, or Tiruppur. OMP does.

Read the full story in [Vision and Scope](docs/architecture/00-overview/vision-and-scope.md) and [Positioning](docs/architecture/00-overview/positioning.md).

## How It Works

```
┌────────────────────────────────────────────────────────┐
│  YOUR PLATFORMS                                        │
│  Factory OS · MES · ERP · Grafana · DPP generators     │
└───────────────▲────────────────────────────────────────┘
                │  MQTT / REST / OPC UA / CSV
┌───────────────┴────────────────────────────────────────┐
│  OMP GATEWAY (one Raspberry Pi per floor)              │
│  Validates · Buffers offline · Signs · Exports         │
└───────────────▲────────────────────────────────────────┘
                │  Adapter plugins
┌───────────────┴────────────────────────────────────────┐
│  YOUR MACHINES                                         │
│  Modbus PLCs · Serial controllers · OPC UA servers ·   │
│  Dumb machines with ESP32 retrofit kits                │
└────────────────────────────────────────────────────────┘
```

Every message is wrapped in a checksummed envelope (optionally signed with the gateway's Ed25519 key):

```json
{
  "omp_version": "0.1.0",
  "profile": "textile-sewing/0.1",
  "gateway_id": "gw-dhaka-f1-01",
  "machine_id": "f1-line3-m07",
  "seq": 48291,
  "ts": "2026-07-24T09:14:03.221Z",
  "schema": "event",
  "body": { "event_type": "cycle_complete", "payload": { "stitch_count": 412 } },
  "checksum": "9f2a...c4"
}
```

The `gateway_id` + `seq` + `checksum` triple is what makes downstream claims auditable. Gaps are detectable. Tampering is detectable. That is the difference between self-declared and machine-attested.

## Quickstart (no hardware needed)

```bash
git clone https://github.com/Mohiemen/Open-Machine-Protocol
cd Open-Machine-Protocol
pip install -e ./gateway -e ./tools

# Start a simulated 10-machine sewing line
omp-simulate --profile textile-sewing --machines 10 | omp-validate

# Or stream it into a local MQTT broker and watch live
omp-simulate --profile textile-sewing --machines 10 --export mqtt://localhost:1883
mosquitto_sub -t 'omp/#' -v
```

Then point Grafana at the broker using `examples/grafana-dashboards/` (ships with the implementation) and you have a live factory floor in your terminal.

Ready for real hardware? Start with [Your First Real Machine](docs/getting-started/first-real-machine.md).

## Supported Machines

| Adapter | Protocol | Machines covered | Status |
|---|---|---|---|
| `generic-modbus` | Modbus RTU/TCP | Countless PLCs, drives, meters, controllers across every industry. YAML register maps, no code required. | 🟢 v0.1 |
| `generic-serial` | RS232/RS485 | Legacy controllers with documented serial output | 🟢 v0.1 |
| `retrofit-esp32` | Sensors via WiFi | Any machine at all - CT clamp (energy), vibration, optical stitch/cycle counter | 🟢 v0.1 |
| `opcua-client` | OPC UA | Modern machines with existing OPC UA servers | 🟡 planned v0.2 |
| `juki-janets` | Juki network | Juki sewing machine networks | 🟡 planned |
| `sedo-treepoint` | Ethernet | Sedo Treepoint dyeing controllers | 🟡 planned |
| `setex-secom` | Ethernet | Setex SECOM dyeing controllers | 🟡 planned |
| `fanuc-focas` | FOCAS | Fanuc CNC controllers | 🟡 planned |
| `siemens-s7` | S7comm | Siemens S7 PLC family | 🟡 planned |

Your machine not here? That's the point of the project. See [Writing an Adapter](docs/guides/writing-an-adapter.md) - target time from "I have this machine" to merged adapter is four weekends, and `omp-sniff` (in `tools/`) helps you capture and decode unknown protocols.

## Domain Profiles

The core schemas are industry-neutral. Industry semantics (machine classes, event vocabularies, process phases) live in versioned profiles:

| Profile | Status |
|---|---|
| `generic` (core events only, works for any machine today) | 🟢 v0.1 |
| `textile-sewing` | 🟢 v0.1 |
| `textile-dyeing` | 🟢 v0.1 |
| `machining` | 🟡 v0.2 |
| `plastics` | 🟡 v0.2 |
| `packaging`, `utilities` | 🟡 v0.3 |

Want a profile for your industry? See [Writing a Profile](docs/guides/writing-a-profile.md).

## For Platform Builders

One ingestion module gives you every machine the community ever connects. Subscribe to `omp/{site}/{area}/{line}/{machine}/{schema}`, deduplicate on (`gateway_id`, `machine_id`, `seq`), and land the envelopes in your store. Platform-specific enrichment goes in namespaced `x-*` extension blocks, never in core.

For Digital Product Passport use cases, the [DPP Evidence Chain guide](docs/integrations/dpp-evidence-chain.md) covers how to cite OMP envelopes as source-verified evidence.

Start at [Platform Ingestion](docs/integrations/platform-ingestion.md).

## Project Principles

These are constitutional. Decisions that violate them are wrong by definition:

1. The specification is open and royalty-free (Apache 2.0), forever.
2. The edge is read-only. OMP will never command a machine.
3. The core is vendor-neutral. Extensions are namespaced.
4. Factories own their data. No cloud, no phone-home, no accounts.
5. Governance is multi-stakeholder. No single-vendor veto, ever.

Full details in [GOVERNANCE.md](GOVERNANCE.md).

## Contributing

The most valuable contributions, in order:

1. **Adapters** for machine families we don't cover - [start here](docs/guides/writing-an-adapter.md)
2. **Profiles** for industries we don't cover - [start here](docs/guides/writing-a-profile.md)
3. **Deployment reports** from real factories, including failures
4. **Translations** - Bangla, Vietnamese, Hindi, Turkish, Bahasa docs convert real factory engineers into users. [translations/](docs/translations/)
5. **Protocol captures** from machines you have access to, even without writing the adapter yourself

See [CONTRIBUTING.md](CONTRIBUTING.md) for the mechanics and [good first issues](https://github.com/Mohiemen/Open-Machine-Protocol/labels/good%20first%20issue) to get moving.

## Documentation

| | |
|---|---|
| [Getting Started](docs/getting-started/) | Quickstart, first machine, installation |
| [Guides](docs/guides/) | Adapters, profiles, retrofits, factory deployment |
| [Reference](docs/reference/) | Schemas, config, CLI, MQTT topics |
| [Architecture](docs/architecture/) | Full architectural documentation, ADRs |
| [Integrations](docs/integrations/) | Platforms, DPP, Grafana, Node-RED |

## Status

OMP is pre-1.0 and under active development. The v0.1 milestone targets a published spec with conformance vectors, a working gateway, three adapters, one retrofit design, and two end-to-end reference deployments. Follow the [milestone plan](docs/architecture/10-roadmap/milestone-plan.md).

## License

Apache License 2.0. See [LICENSE](../LICENSE).

---

*Built by and for the people who keep the world's machines running.*
