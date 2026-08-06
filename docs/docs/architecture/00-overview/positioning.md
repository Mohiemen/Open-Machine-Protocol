# Positioning - OMP in the Industrial Data Landscape

| | |
|---|---|
| **Status** | Draft |
| **Owner** | M A Mohiemen Tanim |
| **Last updated** | July 2026 |
| **Location** | docs/architecture/00-overview/positioning.md |

---

## 1. Why This Document Exists

The first question every experienced engineer asks is "why not just use OPC UA?" or "isn't this MTConnect?" This document answers that question honestly. OMP overlaps with several existing standards, bridges to most of them, and exists because a specific gap remains unfilled - the long tail of industrial machines that no current standard actually reaches.

## 2. The Landscape at a Glance

| | OPC UA | MTConnect | MQTT Sparkplug B | Proprietary IoT platforms | **OMP** |
|---|---|---|---|---|---|
| **Primary domain** | Cross-industry automation | Machining / CNC | Any (payload convention) | Vendor-defined | Any industrial machinery |
| **Data semantics** | Rich, via companion specs | Rich, machining-focused | Minimal (metrics only) | Closed | Core + Domain Profiles |
| **Legacy/dumb machine story** | None | None | None | Retrofit at high cost | First-class (retrofit designs in-repo) |
| **Reverse-engineered protocol support** | Out of scope | Out of scope | Out of scope | Closed, internal | Explicit, documented, community process |
| **Edge footprint** | Heavy (full stack) | Moderate (agent + adapter) | Light | Varies | Light (Pi-class) |
| **Write/control path** | Yes | No (read-only) | Yes | Usually | Never (constitutional) |
| **Data lineage / verifiability** | Possible, not default | No | No | Vendor-attested | Built into envelope (seq, checksum, signature) |
| **Cost to adopt** | High (tooling, expertise) | Moderate | Low | Subscription | Free, low expertise floor |
| **Governance** | OPC Foundation (member fees) | AMT | Eclipse Foundation | Single vendor | Open community, Apache 2.0 |

## 3. Relationship to Each Standard

### 3.1 OPC UA - complement and bridge, not competitor

OPC UA is the dominant standard in modern automation, and it earned that position. Where a machine or PLC already exposes OPC UA, OMP does not replace it - the `opcua-client` adapter consumes it and re-emits OMP envelopes, and the OPC UA exporter lets OMP data flow into existing SCADA/MES estates.

The gap OMP fills:

- **Weight.** A full OPC UA stack with information modeling is a heavy lift for a Pi-class gateway watching 50 sewing machines. Most small factories have no OPC UA anywhere and no staff who know it.
- **The unreached machines.** OPC UA assumes the machine vendor implemented it. The 1998 lockstitch machine, the legacy dyeing controller on RS485, the mechanically perfect but digitally mute majority - OPC UA has no story for them. OMP's retrofit designs and reverse-engineered adapters exist precisely for these.
- **Verifiability by default.** OMP's envelope makes signed, sequence-numbered lineage the baseline, not an advanced configuration.

Roadmap intent - alignment with relevant OPC UA companion specifications where profiles overlap (see open questions in the architecture document), so mappings stay clean in both directions.

### 3.2 MTConnect - respected prior art in one domain

MTConnect proved the read-only, open-vocabulary model works, and OMP deliberately adopts both principles. But MTConnect is machining-centric by design and governance. There is no MTConnect for dyeing machines, injection molders, or packaging lines, and its XML/HTTP agent model is heavier than needed for retrofit-class devices.

OMP's `machining` profile (roadmap v0.2) will document a mapping to MTConnect vocabulary so shops running both are not maintaining two mental models.

### 3.3 MQTT Sparkplug B - transport convention, not a data standard

Sparkplug solves topic structure, birth/death state, and payload encoding over MQTT. It says nothing about what a stitch count, batch phase, or mold cycle means. OMP and Sparkplug operate at different layers - a Sparkplug-compatible topic mapping for the MQTT exporter is a reasonable future addition, and OMP's semantics ride happily on top.

### 3.4 Proprietary machine-monitoring platforms

These are OMP's true competitive contrast, and the comparison is structural rather than feature-based:

- Their drivers are the product, so they cannot open them. OMP's adapters are commons.
- Their data lives in their cloud. OMP's data never leaves the factory unless the factory sends it.
- Their pricing excludes the majority of world manufacturing. OMP's marginal cost is a Pi and an afternoon.
- Their attestations are "trust us." OMP's are "verify against a public spec."

Platforms built above OMP (factory OS, MES, analytics, DPP generators) are not competitors - they are the intended consumers, and several existing proprietary platforms could adopt OMP ingestion tomorrow and benefit.

## 4. The Gap OMP Occupies, in One Picture

```
                    Data semantics richness
                              ▲
                              │
        MTConnect ●           │        ● OPC UA + companion specs
     (machining only)         │       (modern, vendor-implemented)
                              │
                              │   ★ OMP
                              │   (any machine, any age,
                              │    profiles + verifiable lineage)
                              │
      Sparkplug B ●           │
   (transport only)           │
                              │
──────────────────────────────┼──────────────────────────────▶
   Reaches only modern,                     Reaches legacy, dumb,
   vendor-enabled machines                  and retrofit machines
```

No existing open standard sits in the upper-right - rich semantics AND reach into the legacy long tail. That corner is OMP's home.

## 5. Positioning Statements

**For factory engineers** - OMP is the free, open way to get data out of every machine on your floor, including the ones every vendor gave up on, without a cloud subscription or a control-system project.

**For platform builders** - OMP is one integration surface for all machinery, with source-verified lineage strong enough to cite in a Digital Product Passport.

**For the standards community** - OMP is not a rival stack. It is the missing on-ramp that gets the world's unconnected machines into the ecosystems OPC UA and MTConnect already serve, with bridges in both directions.

**In one line** - what OBD-II did for cars, OMP does for industrial machines.

## 6. Anticipated Objections, Answered

1. **"Yet another standard" (xkcd 927).** Fair, and the answer is scope discipline - OMP defines semantics for the unreached long tail and bridges to incumbents rather than replacing them. Success is measured partly by how cleanly OMP data flows INTO OPC UA and MTConnect estates.
2. **"Reverse engineering is legally risky."** The project maintains a documented, jurisdiction-aware process (interoperability purpose, no copy of vendor firmware, clean-room documentation). See guides/reverse-engineering-protocols.md.
3. **"Read-only limits value."** It limits scope, deliberately. Control belongs to certified automation systems with safety cases. Observation is where the unserved need is, and where an open community can operate responsibly.
4. **"Won't machine vendors resist?"** Some will. But OBD-II's history shows the sequence - retrofit adoption creates buyer expectation, buyer expectation becomes procurement language, procurement language brings vendors to the table. Vendors who ship OMP-native output early gain preference among data-hungry buyers.
