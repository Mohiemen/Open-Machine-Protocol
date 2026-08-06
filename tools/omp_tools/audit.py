"""Evidence-bundle auditing - the five checks from DPP Evidence Chain s4.

Given an NDJSON bundle of envelopes covering one process run, this runs the
verification an auditor performs and emits the citation block from s3, so a
platform can attach it to a passport claim and an auditor can independently
reproduce every flag years later.

The checks, verbatim from the guide:

1. Completeness - envelopes exist for every seq in event_seq_range with
   matching gateway_id and machine_id. Gaps invalidate the flag.
2. Integrity   - recompute each checksum via RFC 8785 + SHA-256 over body.
3. Authenticity- verify each Ed25519 signature against the gateway pubkey.
4. Consistency - the process_run summary is derivable from its events.
5. Conformance - all envelopes validate against core and profile schemas.

Design note on honesty: a check that cannot be run (no signatures present,
no pubkey supplied, no comparable quantities) reports `null`, never `true`.
The guide is explicit that overclaiming is the fastest way to destroy the
credibility this chain exists to build, so "not checked" and "checked and
passed" must never collapse into the same value.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .envelope import checksum as compute_checksum
from .validate import validate_envelope


@dataclass
class Check:
    name: str
    passed: bool | None          # None = could not be evaluated
    detail: str
    findings: list[str] = field(default_factory=list)

    @property
    def symbol(self) -> str:
        return {True: "✔", False: "✖", None: "–"}[self.passed]


def records_hash(envelopes: list[dict]) -> str:
    """SHA-256 over the ordered checksums of all cited envelopes (s3).

    Lets a passport commit to an exact evidence set without embedding it.
    Ordered by seq so the digest is reproducible from the same bundle.
    """
    ordered = sorted(envelopes, key=lambda e: e["seq"])
    return hashlib.sha256(
        "".join(e["checksum"] for e in ordered).encode("utf-8")
    ).hexdigest()


def select_run(envelopes: list[dict], run_id: str | None) -> dict:
    runs = [e for e in envelopes if e["schema"] == "process_run"]
    if run_id:
        runs = [e for e in runs if e["body"].get("run_id") == run_id]
        if not runs:
            raise ValueError(f"no process_run with run_id {run_id!r} in the bundle")
    if not runs:
        raise ValueError(
            "no process_run envelope in the bundle - an evidence bundle is "
            "scoped to a run; pass the run's summary envelope too"
        )
    if len(runs) > 1:
        ids = ", ".join(sorted(r["body"]["run_id"] for r in runs))
        raise ValueError(f"bundle covers several runs ({ids}); pass --run-id")
    return runs[0]


# ------------------------------------------------------------------ checks
def check_completeness(cited: list[dict], run_env: dict) -> Check:
    body = run_env["body"]
    rng = body.get("event_seq_range")
    if not rng:
        return Check("completeness", None,
                     "process_run has no event_seq_range - nothing to cite")
    gw, mid = run_env["gateway_id"], run_env["machine_id"]
    want = set(range(rng["first"], rng["last"] + 1))
    have = {e["seq"] for e in cited
            if e["gateway_id"] == gw and e["machine_id"] == mid}
    missing = sorted(want - have)
    if missing:
        shown = missing[:20]
        more = "" if len(missing) == len(shown) else f" (+{len(missing)-len(shown)} more)"
        return Check("completeness", False,
                     f"{len(missing)} envelope(s) missing from "
                     f"seq {rng['first']}-{rng['last']}",
                     [f"missing seq {shown}{more}"])
    return Check("completeness", True,
                 f"seq {rng['first']}-{rng['last']} complete ({len(want)} envelopes)")


def check_integrity(cited: list[dict]) -> Check:
    bad = []
    for e in cited:
        try:
            if compute_checksum(e["body"]) != e["checksum"]:
                bad.append(f"seq {e['seq']}: checksum mismatch")
        except ValueError as exc:
            bad.append(f"seq {e['seq']}: not canonicalizable ({exc})")
    if bad:
        return Check("integrity", False,
                     f"{len(bad)} of {len(cited)} envelopes failed", bad[:20])
    return Check("integrity", True, f"all {len(cited)} checksums recomputed and match")


def check_authenticity(cited: list[dict], pubkey: str | None) -> Check:
    signed = [e for e in cited if "sig" in e]
    if not pubkey:
        return Check("authenticity", None,
                     f"no pubkey supplied ({len(signed)}/{len(cited)} envelopes "
                     "carry a signature)")
    if not signed:
        return Check("authenticity", None,
                     "no envelopes are signed - checksums prove integrity, "
                     "not origin")
    from .sigverify import verify_envelope_sig

    bad = [f"seq {e['seq']}: signature does not verify"
           for e in signed if not verify_envelope_sig(e, pubkey)]
    unsigned = len(cited) - len(signed)
    if bad:
        return Check("authenticity", False, f"{len(bad)} signature(s) failed", bad[:20])
    detail = f"all {len(signed)} signatures verify against the supplied key"
    findings = ([f"{unsigned} envelope(s) in the bundle are unsigned"]
                if unsigned else [])
    return Check("authenticity", True, detail, findings)


def check_consistency(cited: list[dict], run_env: dict) -> Check:
    """Is the summary derivable from the events it cites?

    Only comparisons the bundle actually supports are made; anything else is
    reported as not-evaluated rather than silently passing.
    """
    body = run_env["body"]
    gw, mid = run_env["gateway_id"], run_env["machine_id"]
    same = [e for e in cited
            if e["gateway_id"] == gw and e["machine_id"] == mid]
    findings, compared = [], 0

    # phase boundaries vs phase_start / phase_end events
    declared = [p["name"] for p in body.get("phases", [])]
    if declared:
        started = [e["body"]["payload"]["phase"] for e in same
                   if e["schema"] == "event"
                   and e["body"].get("event_type") == "phase_start"
                   and "phase" in e["body"].get("payload", {})]
        if started:
            compared += 1
            missing = [p for p in declared if p not in started]
            extra = [p for p in started if p not in declared]
            if missing:
                findings.append(f"phases in summary with no phase_start event: {missing}")
            if extra:
                findings.append(f"phase_start events absent from the summary: {extra}")

    # quantities vs summed energy intervals
    quantities = {q["name"]: q["value"] for q in body.get("quantities", [])}
    energy_totals: dict[str, float] = {}
    for e in same:
        if e["schema"] == "energy":
            b = e["body"]
            energy_totals[b["metric"]] = energy_totals.get(b["metric"], 0) + b["value"]
    for metric, total in energy_totals.items():
        for qname in (f"{metric}_total", metric):
            if qname in quantities:
                compared += 1
                claimed = quantities[qname]
                if claimed and abs(claimed - total) / max(abs(claimed), 1) > 0.01:
                    findings.append(
                        f"quantity {qname}={claimed} but cited energy intervals "
                        f"sum to {total}")
                break

    # run boundaries vs run_start / run_end
    has_start = any(e["schema"] == "event"
                    and e["body"].get("event_type") == "run_start" for e in same)
    has_end = any(e["schema"] == "event"
                  and e["body"].get("event_type") == "run_end" for e in same)
    if has_start or has_end:
        compared += 1
        if not has_start:
            findings.append("no run_start event in the cited range")
        if not has_end and body.get("outcome") == "completed":
            findings.append("outcome is 'completed' but no run_end event is cited")

    if not compared:
        return Check("consistency", None,
                     "bundle carries nothing comparable against the summary")
    if findings:
        return Check("consistency", False,
                     f"{len(findings)} discrepancy(ies) across {compared} comparison(s)",
                     findings)
    return Check("consistency", True,
                 f"summary agrees with its events ({compared} comparison(s))")


def check_conformance(cited: list[dict], spec) -> Check:
    bad = []
    for e in cited:
        errors = validate_envelope(e, spec)
        if errors:
            bad.append(f"seq {e['seq']}: {errors[0]}")
    if bad:
        return Check("conformance", False,
                     f"{len(bad)} of {len(cited)} envelopes non-conformant", bad[:20])
    return Check("conformance", True,
                 f"all {len(cited)} envelopes valid against core + profile")


# ------------------------------------------------------------------ driver
def audit_bundle(envelopes: list[dict], spec, *, pubkey: str | None = None,
                 run_id: str | None = None) -> tuple[list[Check], dict]:
    run_env = select_run(envelopes, run_id)
    body = run_env["body"]
    rng = body.get("event_seq_range")
    gw, mid = run_env["gateway_id"], run_env["machine_id"]
    if rng:
        cited = [e for e in envelopes
                 if e["gateway_id"] == gw and e["machine_id"] == mid
                 and rng["first"] <= e["seq"] <= rng["last"]]
    else:
        cited = [e for e in envelopes
                 if e["gateway_id"] == gw and e["machine_id"] == mid]
    if run_env not in cited:
        cited = cited + [run_env]

    checks = [
        check_completeness(cited, run_env),
        check_integrity(cited),
        check_authenticity(cited, pubkey),
        check_consistency(cited, run_env),
        check_conformance(cited, spec),
    ]
    by = {c.name: c for c in checks}

    machine = next((e for e in envelopes
                    if e["schema"] == "machine" and e["machine_id"] == mid), None)
    citation = {
        "evidence": {
            "standard": "OMP",
            "omp_version": run_env["omp_version"],
            "profile": run_env["profile"],
            "gateway_id": gw,
            "machine_id": mid,
            "run_id": body["run_id"],
            "records_hash": records_hash(cited),
            "verification": {
                "seq_complete": by["completeness"].passed,
                "checksums_valid": by["integrity"].passed,
                "signatures_valid": by["authenticity"].passed,
                "consistent": by["consistency"].passed,
                "conformant": by["conformance"].passed,
            },
        }
    }
    if rng:
        citation["evidence"]["event_seq_range"] = rng
    if pubkey:
        citation["evidence"]["gateway_pubkey"] = f"ed25519:{pubkey}"
    if machine:
        # the honesty ladder propagates to claim level (guide s3)
        citation["evidence"]["verification"]["data_source"] = \
            machine["body"].get("data_source")
    return checks, citation


def format_report(checks: list[Check], citation: dict, envelopes: int) -> str:
    lines = [f"audit: {envelopes} envelope(s) in bundle", ""]
    for c in checks:
        lines.append(f"  {c.symbol} {c.name}: {c.detail}")
        lines.extend(f"      {f}" for f in c.findings)
    failed = [c for c in checks if c.passed is False]
    skipped = [c for c in checks if c.passed is None]
    lines.append("")
    if failed:
        lines.append(f"AUDIT FAILED - {len(failed)} check(s) did not pass: "
                     + ", ".join(c.name for c in failed))
    else:
        lines.append("audit passed"
                     + (f" ({len(skipped)} check(s) not evaluated - see above)"
                        if skipped else ""))
    if skipped:
        lines.append("A claim built on this bundle must not assert what was "
                     "not checked.")
    lines += ["", "citation block (DPP Evidence Chain s3):",
              json.dumps(citation, indent=2)]
    return "\n".join(lines)
