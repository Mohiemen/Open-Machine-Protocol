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

## Not here yet (M2 Phase 2)

Service management (`install-service`, `status`, `tail`, `dead-letters` CLI,
registry hot-reload), Ed25519 signing, REST/OPC UA/CSV exporters, retention
pruning, transport pool, and the production adapter host (restart policy,
probe timeouts). Tracked in the
[milestone plan](../docs/docs/architecture/10-roadmap/milestone-plan.md).
