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
- `omp.exporters` - stdout, MQTT (topic convention
  `omp/{site}/{area}/{line}/{machine}/{schema}`, QoS 1, ack after publish),
  and REST (batched NDJSON, gzip, ack only after a 2xx; refuses plain HTTP to
  non-loopback per Hardening Guide s5). Exports are coalesced by a drain
  worker (`--drain-interval`) so batching exporters see real batches.
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
  `--sign`), `reload`, `status`, `dead-letters`.
- **Retention** - `--retention-days` (default 30) and `--max-buffer-bytes`
  prune delivered envelopes only, never past the slowest exporter's cursor;
  every prune is logged and shown by `status`.
- **Resilience** - adapter crashes are isolated and retried with backoff
  (`--max-crashes` then the machine is marked failed); `--probe-timeout`
  stops one hung port stalling floor startup.
- **Hot-reload** - `omp-gateway reload --state-dir …` re-reads the registry
  in place. The new file is validated fully first and refused if invalid;
  unchanged machines keep streaming without a seq break.

- **Host audit** - `omp-gateway audit-host --state-dir …` checks the
  [Hardening Guide](../docs/docs/security/hardening-guide.md) s3 Required
  items (SSH policy, unattended-upgrades, unprivileged service user, serial
  device-group access, dedicated device) plus keypair permissions and NTP,
  stores a baseline and reports **drift** against it. Exit 0 clean, 1 drift,
  2 a Required check failing - so it belongs in cron. A check it cannot
  evaluate says UNKNOWN; it never counts as a pass.

## Not here yet

OPC UA exporter and CSV exporter (CSV is a
[good first issue](https://github.com/Mohiemen/Open-Machine-Protocol/issues/4)),
release signature verification (`verify-release`), and retrofit OTA. Tracked
in the [milestone plan](../docs/docs/architecture/10-roadmap/milestone-plan.md).
