# Consumer Conformance Cases

| | |
|---|---|
| **Status** | Cases defined; executable NDJSON suites land with the reference consumer (roadmap M2) |
| **Authority** | Platform Ingestion guide section 6; Core Schema Specification sections 3-4 |

A consumer claiming "OMP v0.1 conformant ingestion" must demonstrate these
behaviors. Each case will become a scripted suite (input stream + expected
consumer state) once `examples/platform-ingest-reference/` exists to execute
them against.

| Case | Input | Required behavior |
|---|---|---|
| **Duplicate delivery** | Same (`gateway_id`, `machine_id`, `seq`) delivered twice, byte-identical | Second delivery dropped silently; stored record unchanged |
| **Integrity alarm** | Same dedup triple, *different* checksum | NOT treated as duplicate: both stored, loud flag raised, neither overwritten (spec s3) |
| **Gap tracking** | seq 14 then 16 for one machine | Gap recorded and queryable; `seq_complete: false` propagates to any evidentiary output |
| **Out-of-order arrival** | seq 16 before seq 15 (exporter retry interleaving) | Both accepted; ordering by `seq`, not arrival or `ts` |
| **Unknown profile event type** | Valid envelope, unknown `event_type` under a known profile major | Accepted and stored as opaque event - never dropped, never crashes (spec s9) |
| **Unclosed run** | `run_start` with no `run_end` before stream end | Run held open for configured window, then closed as consumer-side `outcome: unknown`, distinct from machine-reported outcomes |
| **Machine record change** | Second `machine` message with changed `location` | New validity period opened; history preserved (slowly changing dimension) |
| **Replay burst** | 6 hours of buffered envelopes replayed after an outage, interleaved across machines | Identical end state to live delivery (idempotency via dedup key) |
