# Factory Deployment - From One Machine to the Whole Floor

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/guides/factory-deployment.md |
| **Audience** | The person responsible for scaling past the pilot - typically 10 to 500 machines |
| **Before this** | [First Real Machine](../getting-started/first-real-machine.md) working, ideally for a week |

---

## 1. Sizing - Gateways, Networks, Brokers

| Scale | Reference layout |
|---|---|
| Up to ~50 machines, one floor | 1 gateway (Pi 5, 4 GB), broker on the gateway itself |
| 50 to 100 machines or mixed serial+WiFi | 1 gateway, external broker on a floor server, dedicated node SSID |
| Multiple floors/buildings | 1 gateway per floor, one central broker, gateway IDs encode location (`gw-{site}-{building}{floor}-{n}`) |
| Dye house + sewing floors | Separate gateways per area even if co-located - blast radius isolation and different maintenance windows |

Rules of thumb from the performance targets doc - a Pi 5 gateway sustains well over 500 events/second, which no realistic 100-machine floor approaches; the binding constraints are USB serial port count (use quality powered hubs, 8 ports per hub max), WiFi airtime for retrofit nodes, and SD card endurance (use an SSD via USB3, or high-endurance cards, full stop).

## 2. Network Topology

```
                    FACTORY OT NETWORK (no internet)
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Machines (Ethernet) ── OT switch ──┐                        │
│  Retrofit nodes ── node SSID (VLAN) ─┤                       │
│  Serial machines ──── USB ──────────┤                        │
│                                  GATEWAY(s)                  │
│                                     │                        │
└─────────────────────────────────────┼────────────────────────┘
                              single egress, firewall
                                      │
┌─────────────────────────────────────┼────────────────────────┐
│  IT NETWORK                      BROKER / platform ingest    │
│                                  Grafana, MES, factory OS    │
└──────────────────────────────────────────────────────────────┘
```

Non-negotiables:

1. **Machines never get internet access** as a side effect of OMP. The gateway is the only thing that crosses zones, outbound only, to the broker/platform address alone.
2. Retrofit nodes on their own SSID and VLAN with client isolation ON between nodes, gateway reachable.
3. No inbound connections to the gateway from IT except your admin SSH (key-only), and none at all from the internet.

Full firewall rule examples and switch configs are in the [Hardening Guide](../security/hardening-guide.md), which is a required read before connecting the egress.

## 3. Rollout Sequence That Works

Adapted from real pilot experience; resist the urge to reorder it.

1. **Week 1 - the pilot line.** One line or one machine cluster, every machine type represented once. Goal is finding your factory's specific surprises (that one VFD that murders RS485, the panel with no cable route) while the blast radius is one line.
2. **Week 2 to 3 - soak and validate.** Do nothing but watch. Dead letters, reconnect patterns, energy plausibility checks, seq persistence through the week's power events. Fix root causes, not symptoms.
3. **Week 4+ - scale by line, not by machine type.** Complete lines give usable data immediately (line efficiency needs the whole line); scattered machines give trivia. One person can comfortably add 10 to 15 machines a day once the registry patterns are established.
4. **Dye house last** (if you have one), despite being the highest-value area - batch semantics deserve your most experienced configuration, and by then you'll have it.
5. **Declare done per area** with the week-of-green criteria from First Real Machine section 8, recorded in a short note. These notes become your deployment report, and a redacted version contributed upstream helps everyone (`deployment-report` label).

## 4. Registry Management at Scale

- The registry is code - keep `/etc/omp/registry.yaml` in git, deploy via a pull, `omp-gateway reload` (validates before applying, refuses invalid).
- Naming discipline pays compound interest - `{site}-{area}{line}-{class}{nn}` (`f1-sew3-ol04`) sorts, greps, and reads on a dashboard.
- Use YAML anchors for repeated config blocks (same baud, same poll interval across 40 identical machines).
- Machine moves and swaps - `machine_id` follows the LOGICAL station, not the physical chassis, when a broken machine is swapped out; record the chassis in `serial`. A machine physically relocated to a new station gets the new station's ID. This one convention prevents most genealogy confusion later.

## 5. Operations Rhythm

Daily (2 minutes, automatable): `omp-gateway status --all` clean, dead-letter count zero or explained, buffer disk under threshold.

Weekly: reconnect-count outliers investigated (they find failing cables before the cables fully fail - genuinely useful maintenance signal), broker/platform consumer lag, one restore-from-power-cut confidence check per month.

Per maintenance event on any machine: verify its data resumed and is sane; panel work loves to disturb clamps and serial leads.

## 6. Environmental Hardening

- **Power** - a small UPS per gateway is effectively mandatory in most target environments; brownouts corrupt SD cards and cheap PSUs first. The buffer survives hard cuts by design, but hardware appreciates not testing that daily.
- **Heat and dust** - fanless enclosures, mounted high and away from lint fall; sewing floor lint is conductive enough to matter over years. Clean intakes on the same schedule as machine servicing.
- **Humidity (dye house)** - conformal-coat retrofit boards (spray, 10 minutes) and use IP65 enclosures with glands there, no exceptions.
- **Cable discipline** - serial runs under 15 m, never tray-shared with VFD output cables, ferrites on runs that misbehave. Every mystery `degraded` in project history has ended at a cable.

## 7. People and Handover

The deployment isn't done until someone who didn't build it can run it:

- One-page laminated runbook at the gateway - status commands, what green looks like, who to call.
- The daily check assigned to a named role (typically the floor's maintenance lead), not to "the team".
- Registry change rights limited to trained people; everything through git so nothing is mysterious.
- Bangla (or local-language) runbook translation - the translations directory has templates; this is the single highest-leverage page to translate.

## 8. When You Outgrow This Guide

Multi-site aggregation, store-and-forward between buildings, redundant gateways, and platform-side scaling are 08-operations territory in the architecture docs, and honestly, if you're there, please write up how you got there - the project needs your deployment report more than you need this guide.
