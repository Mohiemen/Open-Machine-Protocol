# platform-ingest-reference

The compact, honest reference consumer promised by
[Platform Ingestion section 7](../../docs/docs/integrations/platform-ingestion.md) -
all six stages, both storage layers, gap tracking. SQLite instead of
Postgres to stay dependency-free; keep the stage boundaries, replace the
storage with yours.

```bash
omp-simulate --profile textile-dyeing --machines 2 --duration 4h | python3 ingest.py demo.sqlite
python3 ingest.py demo.sqlite --report
```

What it demonstrates (each maps to a rule in the guide):

- malformed input → quarantine with raw bytes, never partially parsed
- invalid envelopes → quarantine, never "repaired"
- dedup on (`gateway_id`, `machine_id`, `seq`); exact redelivery dropped silently
- same key, different checksum → **integrity alarm**, both stored, nothing overwritten
- checksums recomputed at ingestion, result stored per envelope
- raw envelopes immutable; `machines` (slowly changing dimension) and `runs`
  are projections, rebuildable from the raw store
- seq gaps tracked per machine and reported with `seq_complete: false`

MQTT input: pipe `mosquitto_sub -t 'omp/#' -N` (or any transport) into stdin -
the pipeline is transport-agnostic by design, per the guide.
