# Hardening Guide - Securing OMP Deployments

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/security/hardening-guide.md |
| **Audience** | Whoever connects a gateway's egress to anything |
| **Companions** | [Factory Deployment](../guides/factory-deployment.md) (topology), SECURITY.md (reporting), architecture 05-crosscutting/security-architecture.md (threat model rationale) |

This guide is the deployable checklist derived from the threat model. Items are marked **[Required]** or **[Recommended]**. A deployment skipping Required items should be treated as exposed.

---

## 1. Threat Summary (what you're defending against)

In priority order for typical deployments:

1. **The gateway as a pivot point** - it's a Linux box inside the OT network; compromise of it endangers machines far beyond data.
2. **Data integrity attacks** - altering or fabricating records, which for DPP-citing factories is fraud-enabling.
3. **Data confidentiality** - production data is commercially sensitive (capacity, efficiency, recipes-by-inference).
4. **Availability** - lost data during an outage is unrecoverable evidence.

## 2. Network

- **[Required]** OT/IT segmentation per the Factory Deployment topology - machines and gateway in OT, single outbound-only egress from gateway to broker/platform. No other OT-to-IT flows introduced by OMP.
- **[Required]** No internet exposure of the gateway, the broker's OT-facing side, or any retrofit node. Ever. If remote access is needed, it's your existing VPN into IT, then the admin path below.
- **[Required]** Retrofit node SSID - WPA2/3-PSK minimum, dedicated VLAN, client isolation on, unique PSK per site (rotate on staff departure where the PSK was handled by staff).
- **[Recommended]** Egress firewall pinned to broker IP:port, not just "outbound allowed". Example nftables rules in `docs/security/examples/`.
- **[Recommended]** Modbus TCP machines on a further sub-segment reachable only by the gateway - Modbus has no auth; anything that can reach those machines can command them, and that is exactly the capability OMP refuses to have. Don't let the network grant what the software declines.

## 3. Gateway Host

- **[Required]** Dedicated device. The gateway shares hardware with nothing - no Grafana, no "just one more container" on the same Pi.
- **[Required]** SSH - key-only, no root login, no password auth, reachable from admin subnet only.
- **[Required]** Automatic security updates for the OS (`unattended-upgrades`); OMP itself updates deliberately (below), the OS updates automatically.
- **[Required]** The gateway service runs as the unprivileged `omp` user the installer creates, with device-group access to its serial ports only. Do not run as root to "fix" a permissions error; fix the udev rule (`docs/security/examples/99-omp-serial.rules`).
- **[Recommended]** Disk encryption is usually impractical on headless factory Pis (unattended reboot); instead treat physical access seriously - locked enclosure, and see key handling below for what an attacker with the SD card gets.
- **[Recommended]** `omp-gateway audit-host` runs these checks and reports drift; wire it into the weekly rhythm.

## 4. Keys and Data Integrity

- **[Required]** The gateway keypair stays on the gateway. It is never copied into backups, git, or "just in case" USB sticks. A stolen key means an attacker can fabricate attested history for that gateway ID; a lost key just means commissioning a successor key.
- **[Required]** Maintain the key registry from day one - gateway_id, pubkey, commissioned/decommissioned dates, location (DPP Evidence Chain section 6). On any suspicion of host compromise, rotate and record a compromise window; the registry format supports it.
- **[Required]** Enable envelope signatures (`signing: required` in gateway config) for any deployment whose data may support compliance claims. Checksums alone detect corruption; signatures attribute origin.
- **[Recommended]** Time - NTP against the factory's own or a controlled source; clock confidence propagates into verification records, and "ntp_synced" is worth having true.

## 5. Transport

- **[Required]** TLS on the gateway-to-broker/platform leg wherever that leg crosses zones (it almost always does). MQTTS with the broker's cert pinned (`ca_file` in exporter config); REST exporter refuses plain HTTP to non-loopback by default - do not override that flag in production.
- **[Recommended]** Broker auth - per-gateway credentials, write-only to its own `omp/{site}/...` subtree; platform consumers read-only. Mosquitto ACL example in `docs/security/examples/`.
- Plain MQTT is acceptable **only** gateway-local (broker on the gateway itself, port bound to localhost) - the config requires an explicit `allow_plaintext_local: true` so the choice is visible in review.

## 6. Updates and Supply Chain

- **[Required]** Install OMP releases only from GitHub Releases with signature verification (`omp-gateway verify-release` or manual minisign check per release notes). Never `pip install` onto a production gateway from a branch.
- **[Required]** Retrofit OTA updates only via the gateway's staged/rollback mechanism; nodes accept images signed by the release key by default - keep it that way.
- **[Recommended]** Stage releases on one gateway for a week before fleet rollout. Boring, effective.

## 7. Monitoring for Trouble

Signals worth alerting on, all exposed by `omp-gateway status --json`:

- Integrity alarms (seq regression with checksum mismatch) - investigate immediately, this is either a serious bug or an active problem, and the spec forbids auto-resolving it quietly.
- Dead-letter rate stepping up on a previously clean machine - data-shape change or tampering upstream of the gateway.
- Unexpected gateway reboots or service restarts outside maintenance windows.
- Host drift reported by `audit-host`.

## 8. Incident Response, Minimal Version

1. Preserve - do not wipe the gateway; image the storage if you can.
2. Isolate - pull the egress, leave OT-side capture intact.
3. Rotate - keys per section 4, PSKs if node network is implicated.
4. Assess evidence impact - which seq ranges fall in the suspect window; mark them in the platform (`verification` flags exist for this reason).
5. If an OMP vulnerability is implicated, report it per SECURITY.md - privately, and thank you.

## 9. What This Guide Deliberately Doesn't Cover

Securing the platforms consuming OMP data, the factory's broader OT security posture beyond OMP's footprint, and physical security programs. OMP's design keeps its footprint small precisely so this list stays short; keep it that way in your deployment.
