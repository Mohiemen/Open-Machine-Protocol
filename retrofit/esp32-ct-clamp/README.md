# esp32-ct-clamp

The universal retrofit starting point: non-invasive energy sensing plus
inferred start/stop events for any machine with a power cable.

**STATUS: DRAFT - written to the retrofit guide's documented behavior,
NOT yet validated on hardware.** What that means concretely:

- The firmware has **not been compiled or run** by its author: the ESP32
  toolchain could not be fetched in the authoring environment, so even
  `pio run` is unverified. Expect to fix compile errors on your first
  build, and please PR the fixes.
- The ADC/RMS calibration path is the standard arrangement but its constants
  are unverified against a reference meter - treat all readings as
  uncalibrated until someone runs the bench validation in
  [retrofit guide section 7](../../docs/docs/guides/retrofit-installation.md).
- Hardware validation is an M3-adjacent task on the
  [roadmap](../../docs/docs/architecture/10-roadmap/milestone-plan.md), and
  a validation report (board photos, meter comparison, a week of soak) would
  be one of the most valuable contributions this project can receive.

| Piece | Where |
|---|---|
| Firmware (PlatformIO) | [firmware/](firmware/) |
| Flash + provision docs | [firmware/FLASHING.md](firmware/FLASHING.md), [firmware/PROVISIONING.md](firmware/PROVISIONING.md) |
| Parts + wiring | [hardware/BOM.md](hardware/BOM.md) |
| Gateway adapter | [adapters/retrofit-esp32](../../adapters/retrofit-esp32/) |
| Install walkthrough | [Retrofit Installation guide](../../docs/docs/guides/retrofit-installation.md) |

Node protocol: plain JSON messages on `omp-node/{node_id}` over the local
broker (`hello`, `energy` with integral Wh, `start`/`stop` events). The node
never builds OMP envelopes - the gateway's retrofit-esp32 adapter translates
and the gateway validates, sequences, and signs, so a compromised or buggy
node cannot forge envelope integrity.

Not here yet: OTA updates (staged/rollback via `omp-gateway retrofit-update`
per the guide - roadmap), vibration and optical-counter kit firmware (same
base, different sensing - contribution-wanted).
