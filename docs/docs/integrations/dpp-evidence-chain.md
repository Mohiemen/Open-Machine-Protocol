# DPP Evidence Chain - Citing OMP Data in Digital Product Passports

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/integrations/dpp-evidence-chain.md |
| **Audience** | Platform builders generating DPPs, auditors verifying them, factory compliance teams |
| **Companion** | Core Schema Specification (envelope, seq, checksum), Profile Specification (phases, quantities) |
| **Last updated** | July 2026 |

---

## 1. The Problem This Solves

Digital Product Passport regimes (EU ESPR and successors) require claims about how a product was made - process conditions, resource consumption, facility of origin. Today, most such claims are **self-declared** - a person types numbers into a form, and the passport's credibility rests entirely on trusting that person and their employer.

OMP enables a stronger class of claim - **machine-attested** - where the passport cites operational records whose origin, completeness, and integrity can be independently checked against a public specification.

This guide defines exactly how to construct such citations, and, just as importantly, exactly what they do and do not prove.

## 2. The Evidence Chain, End to End

```
Machine signal
   │  adapter translates to profile vocabulary
   ▼
OMP envelope        seq assigned · body checksummed (RFC 8785 + SHA-256)
   │                · optionally Ed25519-signed by gateway keypair
   ▼
Gateway buffer      append-only, survives power loss
   │  at-least-once export
   ▼
Platform store      dedup on (gateway_id, machine_id, seq) · gap tracking
   │  batch/run assembly
   ▼
process_run         phases, quantities, event_seq_range
   │
   ▼
DPP claim           cites run_id + envelope references + verification result
```

Every arrow is checkable. That is the entire point.

## 3. Anatomy of an OMP Evidence Citation

A DPP process claim backed by OMP data SHOULD include:

```json
{
  "claim": "Batch dyed with max temperature 60C, 42.3 kWh, 1847 L water",
  "evidence": {
    "standard": "OMP",
    "omp_version": "0.1.0",
    "profile": "textile-dyeing/0.1",
    "gateway_id": "gw-dhaka-f1-01",
    "gateway_pubkey": "ed25519:base64...",
    "machine_id": "f1-dye-jet02",
    "run_id": "018f3c2a-...-uuidv7",
    "event_seq_range": { "first": 102118, "last": 102331 },
    "records_hash": "sha256 over the ordered checksums of all cited envelopes",
    "verification": {
      "seq_complete": true,
      "checksums_valid": true,
      "signatures_valid": true,
      "clock_confidence": "ntp_synced",
      "data_source": "native"
    }
  }
}
```

Field notes:

- **`event_seq_range`** comes straight from the `process_run` record - the run points at its own evidence.
- **`records_hash`** lets a passport commit to the exact evidence set without embedding it. The underlying envelopes stay in the platform's store (or the factory's archive) and are produced on audit request.
- **`verification`** is the platform's attestation of the checks it ran at ingestion time. Each flag is independently re-runnable by an auditor given the envelopes.
- **`data_source`** propagates the honesty ladder from the schemas - `native` controller data, `ct_clamp` retrofit measurement, `estimated`. A claim built on estimates MUST say so.

## 4. Verification Procedure (for Auditors)

Given a claim citation and the cited envelope set:

1. **Completeness** - confirm envelopes exist for every `seq` in `event_seq_range` with matching `gateway_id` and `machine_id`. Gaps invalidate the completeness flag.
2. **Integrity** - recompute each envelope's checksum via RFC 8785 canonicalization + SHA-256 over `body`. Any mismatch is tampering evidence.
3. **Authenticity** (where signed) - verify each Ed25519 signature against `gateway_pubkey`. Confirm the pubkey's registration (see section 6).
4. **Consistency** - confirm the `process_run` summary is derivable from the cited events - phase boundaries match `phase_start`/`phase_end` events, quantities match `energy` interval sums, max temperature matches telemetry/hold events.
5. **Schema conformance** - validate all envelopes against the cited core and profile versions using `omp-validate`.

All five checks are mechanical. `omp-validate --audit` (roadmap, tools/) will execute them as one command over an NDJSON evidence bundle.

## 5. What OMP Evidence Proves, and What It Does Not

This section exists because overclaiming is the fastest way to destroy the credibility this whole chain builds. Platforms citing OMP evidence MUST NOT represent it as proving more than it does.

**Proven (given passing verification):**

- A gateway holding a specific key emitted this exact sequence of records, without gaps, and the records were not altered afterward.
- The records conform to a public specification and profile, so their semantics are unambiguous.
- The summarized run (temperatures, durations, consumption) is arithmetically consistent with its underlying event stream.

**NOT proven:**

- **That the sensors were accurate or calibrated.** OMP attests data lineage, not metrological truth. Calibration records are a separate, complementary evidence type.
- **That the gateway configuration honestly mapped machines.** A malicious operator could label machine A's data as machine B's. Mitigations - registry audits, physical inspection, cross-checks against utility submeters - are organizational, not cryptographic.
- **That this batch corresponds to this physical product.** Linking a run to shipped goods requires the platform's batch-to-order genealogy on top of OMP.
- **Anything about steps OMP never observed.** Absence of records is absence of evidence, not evidence of compliance.

The honest formulation for passport language - *"process data machine-recorded at source under the OMP v0.1 specification and verified for completeness and integrity"* - not "independently proven" or "tamper-proof."

## 6. Key Management Requirements

The chain is only as strong as the gateway keypair, so:

1. Keys are generated on-device at install; private keys never leave the gateway.
2. The factory (or its platform) SHOULD maintain a **key registry** - gateway_id, pubkey, commissioning date, decommissioning date, physical location - and make it available to auditors.
3. Key rotation - new keypair, overlap period, both keys in the registry with validity windows. Envelopes verify against the key valid at their `ts`.
4. A compromised key invalidates authenticity (not existence) of its window's records; the registry MUST support marking compromise windows.
5. Roadmap - optional anchoring of daily `records_hash` digests to an external timestamping service or transparency log, which would add proof-of-existence-by-date without any blockchain dependency.

## 7. Practical Guidance for Platform Builders

- **Verify at ingestion, not at passport time.** Run the checks as data arrives and store the results; reconstructing verification months later against archived data is possible but painful.
- **Store raw envelopes immutably** for at least the passport's regulatory retention period. The `process_run` summary is for querying; the envelopes are the evidence.
- **Track gaps prominently.** A run whose `event_seq_range` has known gaps can still be cited, but `seq_complete: false` must propagate to the claim. Silent gap-hiding is the one behavior that would justify an auditor distrusting the entire platform.
- **Propagate `data_source` to claim level** and let downstream consumers weight accordingly.
- **Keep platform enrichment out of the evidence.** Order references, operator assignments, and costing live in `x-*` blocks or platform tables - they are checksummed if inside `body`, but they are platform assertions, not machine attestations, and audit language must not blur the two.

## 8. Worked Example - One Dye Batch to One Passport Claim

1. Jet dyeing machine `f1-dye-jet02` runs batch `B-4471` under `textile-dyeing/0.1`. Gateway emits 214 envelopes, seq 102118 to 102331 - `run_start`, phases (load, heat, hold at 60C for 45 min, dose x3, cool, rinse x2, drain, unload), interval `energy` records, and `run_end`.
2. At `run_end` the gateway emits the `process_run` summary - `outcome: completed`, phases with actual gradients and durations, quantities (`fabric_kg: 480`, `kwh_total: 42.3`, `water_l_total: 1847`), `event_seq_range: {102118, 102331}`.
3. The platform ingests, deduplicates, verifies (all five checks pass), stores envelopes immutably, and links `B-4471` to purchase order PO-2291 in its own genealogy (an `x-` concern).
4. The passport for the resulting goods carries the claim block from section 3, with `records_hash` over the 214 ordered checksums.
5. Two years later an auditor requests the bundle, runs `omp-validate --audit`, and independently reproduces every verification flag.

That is the difference between a spreadsheet and an evidence chain.
