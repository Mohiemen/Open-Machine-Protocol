# Platform Ingestion - Consuming OMP Data Correctly

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/integrations/platform-ingestion.md |
| **Audience** | Developers integrating OMP into a factory OS, MES, ERP, CMMS, analytics stack, or DPP platform |
| **Companions** | Core Schema Specification (normative rules), [DPP Evidence Chain](dpp-evidence-chain.md) (if you make compliance claims) |

The promise of OMP to a platform is one integration surface for every machine the community ever connects. This guide is the correct implementation of that surface - the parts that are obvious, and the five parts that everyone gets wrong the first time.

---

## 1. Transport Choice

| You want | Use | Notes |
|---|---|---|
| Real-time, factory or cloud | **MQTT subscribe** (primary path) | Subscribe `omp/{site}/#` or narrower; QoS 1 |
| Simple cloud ingestion, no broker | **REST push** | Gateway POSTs batched NDJSON to your endpoint; you return 200 only after durable write |
| Coexistence with SCADA/MES estates | **OPC UA** | Gateway's OPC UA exporter mirrors the registry as an address space |
| Air-gapped or tiny factories | **CSV import** | Same envelopes, rotating files, sneakernet-compatible |

All four carry identical envelopes. Build your core pipeline transport-agnostic - envelopes in, verified records out - and keep transport adapters thin.

## 2. The Ingestion Pipeline, Correctly

```
receive ─▶ parse ─▶ validate ─▶ dedup ─▶ verify ─▶ store raw ─▶ project
                     │            │        │           │
                  reject to    drop dup  record     immutable
                  quarantine            flags       envelope store
```

Per stage:

1. **Parse** - NDJSON, envelope shape. Malformed input goes to your quarantine with the raw bytes; never partially parse.
2. **Validate** - `omp-validate` as a library (or your port passing the conformance vectors) against core + declared profile. Invalid envelopes are quarantined, not fixed up. Resist the urge to "repair" - a repaired record is a fabricated record.
3. **Dedup** - the key is (`gateway_id`, `machine_id`, `seq`). At-least-once delivery guarantees you WILL see duplicates; drop exact re-deliveries silently. Same key with a **different checksum** is not a duplicate - it's an integrity alarm (spec section 3); store both, flag loudly, never overwrite.
4. **Verify** - recompute checksum, verify signature against your key registry, record the flags (`checksums_valid`, `signatures_valid`, key validity window). Doing this at ingestion, not at query time, is the single best architectural decision available to you (DPP guide section 7).
5. **Store raw** - the envelope, byte-preserving, immutable, retention matched to your compliance horizon. Your queryable models are projections of this store, always rebuildable from it.
6. **Project** - now build whatever your product needs - asset registries from `machine`, OEE from `event`, genealogy from `process_run`, utility allocation from `energy`.

## 3. The Five Classic Mistakes

1. **Ordering by `ts`.** Wall clocks in factories lie. Within a machine, `seq` is the order (spec section 4); `ts` is context. Cross-machine "simultaneity" is always approximate - design UIs and joins accordingly.
2. **Treating gaps as ignorable.** A seq gap means missing data - maybe in flight, maybe lost. Track gaps per machine, expose them (a data-completeness indicator per machine/day is the honest UI), and propagate `seq_complete: false` into anything evidentiary. Silent gap-hiding is the behavior that would justify an auditor distrusting your platform entirely.
3. **Hard-coding profiles.** New profile minor versions add event types; the spec requires you to accept unknown event types under a known major as opaque events (spec section 9). Log them, count them, display them generically - never drop or crash. Your textile customer will one day add a machining line, and your ingestion should not care.
4. **Enriching inside the evidence.** Your order numbers, operators, and costing join to OMP records; they do not get written back into them. Raw envelopes stay pristine; enrichment lives in your projections (or arrives from the gateway in `x-` blocks if you control that config). Blurring machine attestations with platform assertions is the fastest way to make both worthless (DPP guide section 7).
5. **Trusting `machine.json` lazily.** Machines re-announce on change and periodically. Treat machine records as a slowly changing dimension - a `machine_class` or location change opens a new validity period, it doesn't overwrite history. Your genealogy depends on this.

## 4. Run Assembly

For batch/job-centric products, `process_run` is your unit:

- Open a run context on `run_start`, attach subsequent events by `run_id` (falling back to time-window attribution only where the adapter couldn't tag - flag which method you used).
- On the `process_run` summary, cross-check it against the events you attached (phase boundaries vs `phase_start/end`, quantities vs energy interval sums). Mismatches are data-quality signals worth surfacing, and consistency checks are step 4 of the audit procedure you'll want to have already run.
- `event_seq_range` from the summary is what you carry into any DPP claim.
- Runs that never close (gateway saw `run_start`, then power cut before `run_end`) - hold open for a configurable window, then close as `outcome: unknown` in your projection, clearly distinct from machine-reported outcomes.

## 5. Scale Notes

- Volume is modest by modern standards - a 500-machine site peaks in the low hundreds of envelopes/second. One consumer instance per site partition (`omp/{site}/#`) with the dedup index in memory + persistent store handles it without ceremony.
- Dedup index growth - (gateway, machine) high-water marks plus a recent-window set is sufficient; you don't need every historical seq in RAM.
- Backfill/replay - gateways replay after outages in seq order per machine but interleaved across machines; your pipeline must be as happy with 6 hours of replay as with live trickle. Idempotency via the dedup key makes this free if you didn't cut corners in stage 3.

## 6. Conformance for Consumers

`spec/conformance/consumer/` contains vector suites for the behaviors above - duplicate delivery, gap sequences, integrity-alarm cases, unknown event types, unclosed runs. A consumer passing them may state "OMP v0.1 conformant ingestion" in its documentation. If you make DPP claims, the [evidence chain guide](dpp-evidence-chain.md) adds the citation format and audit procedure on top.

## 7. Reference Sketch (Python, MQTT to Postgres)

A compact but honest reference consumer - all six stages, both storage layers, gap tracking - lives at `examples/platform-ingest-reference/`. It is deliberately boring, roughly 400 lines, and suitable as the seed of a production implementation. Start there, keep the stage boundaries, replace the storage with yours.
