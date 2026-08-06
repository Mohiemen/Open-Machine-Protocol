# Open Machine Protocol (OMP)

**What OBD-II did for cars, OMP does for industrial machines.**

OMP is an open-source driver layer and data standard that turns any
industrial machine into a source of standardized, verifiable operational
data. A 1998 lockstitch sewing machine, a Modbus PLC, a jet dyeing
controller, a CNC mill - one envelope format, one gateway, one
integration surface for every platform above it.

- 🔌 **Any machine** - protocol adapters for networked controllers,
  $15 ESP32 retrofit kits for machines with no digital output at all
- 📋 **One open schema** - domain-neutral core plus industry profiles
  (textile, machining, plastics, and growing)
- 🔒 **Read-only by design** - OMP observes machines, never commands
  them. Constitutional, not configurable.
- ✅ **Verifiable at source** - sequence numbers, checksums, and
  gateway signatures make every event auditable, strong enough to
  cite in a Digital Product Passport
- 📴 **Offline-first, Pi-class** - built for factories with unstable
  power, unreliable networks, and real budgets

**No cloud. No subscription. Your machines, your data.**

---

## Try it now (no hardware needed)

```bash
git clone https://github.com/Mohiemen/Open-Machine-Protocol
cd Open-Machine-Protocol
pip install -e ./gateway -e ./tools

omp-simulate --profile textile-sewing --machines 10 --duration 10m | omp-validate
```

Full walkthrough: [Quickstart](docs/docs/getting-started/quickstart.md)
(বাংলায়: [কুইকস্টার্ট](docs/docs/translations/bn/getting-started/quickstart.md)).

## In this repository

| | |
|---|---|
| [docs/](docs/) | Full documentation - project README, vision, spec prose, guides, governance |
| [docs/spec/](docs/spec/) | **Normative artifacts** - JSON Schemas, conformance vectors, profile packages |
| [tools/](tools/) | `omp-validate`, `omp-simulate` |
| [gateway/](gateway/) | Edge gateway core - adapter API, validation, buffer, exporters |
| [Roadmap](docs/docs/architecture/10-roadmap/milestone-plan.md) | Living milestone plan - updated with every change |

**Status**: pre-1.0, under active development. Spec v0.1 draft with executable
conformance vectors; tools and gateway core shipped; adapters, retrofit
firmware, and service management in progress - see the roadmap for the honest
per-item state.

## License

Apache 2.0 - see [LICENSE](LICENSE).