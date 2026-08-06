# Security Architecture - Threat Model and Design Rationale

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/architecture/05-crosscutting/security-architecture.md |
| **Audience** | Contributors to gateway/exporter/adapter code, security reviewers, and anyone deciding whether to trust an OMP deployment |
| **Companions** | [Hardening Guide](../../security/hardening-guide.md) (the deployable checklist derived from this model), [SECURITY.md](../../../SECURITY.md) (reporting), Core Schema Specification sections 3-5 (integrity mechanisms) |
| **Last updated** | July 2026 |

This document explains *why* the hardening guide says what it says - the
assets, trust boundaries, and attack paths behind each Required item. It
invents no mechanisms; everything here is the rationale for behavior already
defined in the spec, the adapter API, and the gateway design.

---

## 1. What Makes OMP's Position Unusual

An OMP gateway is a Linux device *inside* a factory OT network, adjacent to
production machinery, in facilities that typically have no security staff. Two
consequences drive the whole model:

1. **The gateway's worst failure mode is not data loss - it is becoming a
   pivot.** Machines on OT networks (Modbus in particular) have no
   authentication; anything that can reach them can command them. OMP
   constitutionally refuses a write path in software, so the design must also
   refuse to *become* one in practice through compromise or misconfiguration.
2. **The data is evidence.** Factories cite OMP records in DPP-class
   compliance claims. That upgrades integrity attacks from "bad dashboards"
   to fraud-enabling, and it is why integrity mechanisms live in the envelope
   itself rather than in transport.

## 2. Assets and Trust Boundaries

```
        TB-1                TB-2                 TB-3
  machine ── link ──▶ adapter │ gateway core ──▶ egress ──▶ broker / platform
                              │                    ▲
  retrofit node ── WiFi ──────┘                    └─ TB-4: admin access (SSH)
```

| Asset | Why it matters |
|---|---|
| **Machines and controllers** | Physical production; unauthenticated protocols; harm here is physical and financial |
| **Gateway host** | Holds the private key, the buffer, and OT network position |
| **Gateway keypair** | A stolen private key allows fabricating attested history for that `gateway_id` |
| **Buffered envelopes** | Unrecoverable evidence until exported; commercially sensitive |
| **Machine registry** | Defines what data claims to come from where - the mapping-honesty root (see section 6) |
| **Retrofit node fleet + PSK** | Radio-reachable devices with OTA update capability |

Trust boundaries:

- **TB-1, machine link.** The gateway trusts machines to *speak*, never to be
  benign. Adapter input is untrusted bytes: malformed frames, hostile lengths,
  garbage under electrical noise. Adapters parse defensively, and adapter
  isolation (API section 6) keeps a wedged or crashing adapter from taking the
  gateway down. Constitutionally, nothing crosses this boundary toward the
  machine except read/poll frames.
- **TB-2, adapter/gateway core.** Adapters are third-party code. The division
  of responsibility (API section 1) keeps everything trust-relevant - seq
  assignment, checksumming, signing, buffering, export - out of adapter hands;
  an adapter cannot forge sequence continuity or sign anything even if
  malicious. Adapters get no network beyond their configured machine link and
  no filesystem beyond a scratch dir. Subprocess/seccomp isolation is roadmap;
  the contract is already written so adapters won't notice that change.
- **TB-3, egress.** The single outbound-only crossing from OT to the broker or
  platform. TLS, pinned; no inbound path exists in the design. Everything the
  outside world ever sees of the gateway passes through here.
- **TB-4, administration.** Key-only SSH from the admin subnet. This is the
  boundary the hardening guide spends the most Required items on, because it
  is the one attackers actually use.

## 3. Threat Actors

In descending order of likelihood, not capability:

1. **Opportunistic malware / lateral movement from IT** - reaches OT through
   flat networks or dual-homed hosts; scans, pivots, ransoms.
2. **Insider with configuration access** - operator or integrator who can edit
   the registry or relabel machines; motive ranges from convenience to
   compliance fraud.
3. **Data-motivated competitor or intermediary** - production capacity,
   efficiency, and recipe-by-inference data has commercial value.
4. **A party motivated to falsify compliance evidence** - the actor the DPP
   evidence chain exists to make expensive; may be the factory itself.
5. **Vendor or third party with physical access** - service technicians at
   panels; mostly a clamp-disturbance and SD-card-theft vector, not an APT.

Nation-state OT attacks are out of model: a factory facing that adversary
needs an OT security program, not a data gateway's threat model.

## 4. Priority Threats and Attack Paths

The hardening guide's section 1 summary, expanded:

### T1 - Gateway as pivot point

- *Paths*: exposed inbound service on the gateway; stolen SSH credential;
  malicious adapter package; compromised release artifact; retrofit OTA abuse.
- *Design counters*: no inbound listeners toward IT/internet by design;
  adapters denied network beyond the machine link; signed releases with
  verification (`omp-gateway verify-release`); retrofit OTA staged, rollback-
  safe, release-key-signed; gateway runs as unprivileged `omp` user.
- *Residual risk*: host compromise via OS vulnerability - mitigated
  operationally (automatic OS security updates, dedicated device, SSH policy)
  and bounded by network segmentation: even a rooted gateway should only be
  able to reach machines and the broker, which is why the hardening guide
  refuses to let the network grant what the software declines (Modbus
  sub-segmentation).

### T2 - Data integrity attacks

- *Paths*: altering records in transit or at rest downstream; fabricating
  records claiming a gateway's identity; deleting inconvenient records;
  replaying old records.
- *Design counters*: per-body checksum (RFC 8785 + SHA-256) makes alteration
  detectable; Ed25519 signature over `gateway_id || machine_id || seq ||
  checksum` makes fabrication require the private key; monotonic per-machine
  `seq` makes deletion visible as gaps and replay visible as duplicates
  (consumers dedup on the triple); seq regression with a different checksum is
  a mandatory integrity alarm, forbidden to auto-resolve (spec section 3).
- *Residual risk*: a stolen gateway private key defeats attribution for its
  validity window - hence key-never-leaves-device, the key registry with
  compromise windows, and rotation procedure (DPP guide section 6).

### T3 - Data confidentiality

- *Paths*: sniffing the egress leg; broker over-broad read ACLs; captures and
  fixtures published with production data; buffer read from a stolen SD card.
- *Design counters*: TLS on any zone-crossing leg; plaintext MQTT only
  loopback with an explicit visible config flag; per-gateway write-only broker
  credentials and read-only consumer ACLs; contribution guidance to scrub
  captures.
- *Accepted risk*: buffer-at-rest is unencrypted on typical headless Pis
  (unattended reboot makes disk encryption impractical); compensated by
  physical control guidance. What a stolen SD card yields is buffered
  envelopes and the private key - which is exactly why the registry supports
  compromise windows.

### T4 - Availability

- *Paths*: power loss, broker outage, disk exhaustion, WiFi interference on
  the node SSID; deliberate jamming is treated the same as interference.
- *Design counters*: offline-first buffering (SQLite WAL, survives power
  cuts), at-least-once replay per exporter cursor, retrofit nodes' local
  10-minute buffer, dead-letter store so invalid data is never silently
  dropped, disk thresholds surfaced in health.
- *Residual risk*: data loss beyond the retention window during extended
  outages - visible afterward as seq gaps, which is the honest outcome the
  design prefers over invisible loss.

## 5. Security Properties by Design

| Property | Mechanism | Threats countered |
|---|---|---|
| Read-only edge (constitutional) | No write/command path in adapter contract; PRs adding one are rejected regardless of merit | T1 (limits blast radius of any compromise to observation) |
| No inbound surface | Outbound-only egress; no listeners toward IT | T1 |
| Least-privilege adapters | No seq/sign/export access; no network beyond machine link; scratch-dir-only filesystem | T1, T2 |
| Completeness evidence | Monotonic persisted `seq`; gaps consumer-visible | T2, T4 |
| Integrity evidence | RFC 8785 canonicalization + SHA-256 per body | T2 |
| Origin evidence | Ed25519 per-gateway signature, key registry | T2 |
| Validation firewall | Core+profile validation before buffering; dead-letter isolation | T2 (invalid data never exports as valid) |
| Offline resilience | WAL buffer, exporter cursors, replay | T4 |
| Supply-chain discipline | Signed releases, staged retrofit OTA | T1 |

## 6. What the Model Explicitly Does Not Defend

Stated plainly, because overclaiming security is how trust dies (the same
discipline as DPP guide section 5):

- **Registry mapping honesty.** A privileged insider can label machine A's
  data as machine B's. Cryptography attests *which gateway* said something,
  not that the gateway's configuration told the truth. Counters are
  organizational: registry-in-git with change history, audits, physical
  inspection, cross-checks against submeters.
- **Sensor truth.** Lineage, not metrology. A miscalibrated or misclamped CT
  reads wrong, verifiably.
- **The machines' own controllers.** Their vulnerabilities belong to their
  vendors (SECURITY.md scope); OMP's duty is not to widen the path to them.
- **Downstream platforms.** Verification-at-ingestion guidance exists
  (platform ingestion guide), but a platform's own security is its own.
- **Physical attacks and the factory's broader OT posture** - see hardening
  guide section 9.

## 7. Keeping This Model Honest

- Any new gateway/exporter/adapter capability that crosses a trust boundary
  in a new way needs its section here *in the same PR* - this document is a
  living companion to the code, and drift between model and implementation is
  a reportable bug.
- Specification-level flaws that make conformant implementations insecure are
  the most valuable vulnerability reports the project can receive
  (SECURITY.md) - this model is the map for finding them.
