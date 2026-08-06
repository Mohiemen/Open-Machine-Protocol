# omp-gateway

The OMP edge gateway core - adapter API, validation, seq assignment,
WAL-buffered persistence, dead letters, and exporters.

```bash
pip install -e ./gateway -e ./tools   # gateway reuses omp-tools for spec loading
```

## Shipped (M2 Phase 1)

- `omp.adapter` - the [Adapter Plugin API](../docs/docs/architecture/04-interfaces/adapter-plugin-api.md):
  `AdapterBase`, `Body`, `MachineInfo`, `AdapterHealth`, health-from-marks,
  backoff. The API doc's minimal example runs unmodified.
- `omp.core` - registry validation, the Engine (validate against core +
  declared profile BEFORE buffering; invalid bodies dead-letter with the
  error attached, and their seq is a visible gap, never reused), SQLite WAL
  store with per-machine persistent seq and per-exporter cursors
  (at-least-once).
- `omp.exporters` - stdout and MQTT (topic convention
  `omp/{site}/{area}/{line}/{machine}/{schema}`, QoS 1, ack after publish).
- `omp-gateway run-once --adapter <dir> --config <yaml>` - the adapter
  development loop from the [Writing an Adapter guide](../docs/docs/guides/writing-an-adapter.md).
- **Ed25519 signing** (`omp.core.keys`) - keypair generated on-device
  (0600, never serialized elsewhere), signature over
  `gateway_id\nmachine_id\nseq\nchecksum` (UTF-8); `omp-validate --pubkey`
  verifies the same construction. The spec's `||` concatenation encoding is
  pinned here pending a clarification RFC.
- **Service commands** - `install-service` (dirs, keypair, registry
  template, systemd unit), `show-identity`, `run` (the daemon: registry ->
  adapters by name -> engine -> exporters, machine announcement on startup,
  `--sign`), `status`, `dead-letters`.

## Not here yet

REST/OPC UA/CSV exporters, registry hot-reload, retention pruning, transport
pool, adapter restart policy/probe timeouts, release signature verification
(`verify-release`), retrofit OTA. Tracked in the
[milestone plan](../docs/docs/architecture/10-roadmap/milestone-plan.md).
