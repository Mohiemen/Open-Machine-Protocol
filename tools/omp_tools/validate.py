"""omp-validate - validate an NDJSON stream of OMP envelopes.

Order per message: envelope schema -> body schema -> checksum -> declared
profile's constraints. First failure wins for reporting; the message counts
as invalid either way. Exit code 1 if anything was invalid.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from . import __version__
from .envelope import checksum as compute_checksum
from .specload import load_spec


def validate_envelope(envelope: dict, spec, forward_compatible: bool = False) -> list[str]:
    errors = [e.message for e in spec.validators["envelope"].iter_errors(envelope)]
    if errors:
        return errors
    body = envelope["body"]
    errors = [e.message for e in spec.validators[envelope["schema"]].iter_errors(body)]
    if errors:
        return errors
    try:
        if compute_checksum(body) != envelope["checksum"]:
            return ["checksum mismatch"]
    except ValueError as exc:  # non-canonicalizable body
        return [f"checksum not computable: {exc}"]
    return spec.profile_errors(envelope, forward_compatible=forward_compatible)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omp-validate", description=__doc__)
    parser.add_argument("files", nargs="*", help="NDJSON files (default: stdin)")
    parser.add_argument("--spec-dir", help="path to the spec directory")
    parser.add_argument("--quiet", action="store_true", help="summary line only")
    parser.add_argument(
        "--pubkey", metavar="BASE64",
        help="verify Ed25519 signatures against this gateway public key; "
             "envelopes without a sig then fail",
    )
    parser.add_argument(
        "--audit", action="store_true",
        help="audit an evidence bundle: run the five DPP checks over the "
             "envelopes of one process run and print the citation block",
    )
    parser.add_argument(
        "--run-id", help="which run to audit when the bundle covers several",
    )
    parser.add_argument(
        "--version", action="version", version=f"omp-validate {__version__}"
    )
    args = parser.parse_args(argv)

    spec = load_spec(args.spec_dir)

    def lines():
        if args.files:
            for path in args.files:
                with open(path, encoding="utf-8") as f:
                    yield from f
        else:
            yield from sys.stdin

    if args.audit:
        return _run_audit(lines(), spec, args)

    stats = {"valid": 0, "invalid": 0, "by_schema": Counter()}
    # `omp-gateway tail | omp-validate` is the documented way to watch a new
    # machine, and tail follows forever - so Ctrl-C must still report what was
    # seen rather than dying with a traceback and no verdict.
    try:
        _validate_stream(lines(), spec, args, stats)
    except KeyboardInterrupt:
        print()          # past the ^C
    return _report(stats)


def _report(stats) -> int:
    if stats["invalid"] == 0:
        detail = ", ".join(f"{k} x{v}" for k, v in sorted(stats["by_schema"].items()))
        print(f"\u2714 {stats['valid']} messages valid"
              + (f" (schema: {detail})" if detail else ""))
        return 0
    print(f"{stats['valid']} valid, {stats['invalid']} invalid (details above)")
    return 1


def _validate_stream(line_iter, spec, args, stats) -> None:
    """Validates each line, accumulating into `stats` so an interrupted run
    can still be summarised by the caller."""
    for lineno, line in enumerate(line_iter, 1):
        line = line.strip()
        if not line:
            continue
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError as exc:
            stats["invalid"] += 1
            print(f"\u2716 line {lineno}: not JSON ({exc.msg})")
            continue
        errors = validate_envelope(envelope, spec) if isinstance(envelope, dict) else [
            "not a JSON object"
        ]
        if not errors and args.pubkey:
            from .sigverify import verify_envelope_sig

            if "sig" not in envelope:
                errors = ["signature required (--pubkey given) but absent"]
            elif not verify_envelope_sig(envelope, args.pubkey):
                errors = ["signature verification failed"]
        if errors:
            stats["invalid"] += 1
            if not args.quiet:
                where = (
                    f"seq {envelope['seq']}"
                    if isinstance(envelope, dict) and isinstance(envelope.get("seq"), int)
                    else f"line {lineno}"
                )
                print(f"\u2716 {where}: {errors[0]}", flush=True)
        else:
            stats["valid"] += 1
            stats["by_schema"][envelope["schema"]] += 1


def _run_audit(line_iter, spec, args) -> int:
    """`omp-validate --audit` - the auditor's one command (DPP guide s4)."""
    from .audit import audit_bundle, format_report

    envelopes = []
    for lineno, line in enumerate(line_iter, 1):
        line = line.strip()
        if not line:
            continue
        try:
            envelopes.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"✖ line {lineno}: not JSON ({exc.msg}) - an evidence bundle "
                  "must parse before it can be audited")
            return 1
    if not envelopes:
        print("✖ empty bundle")
        return 1
    try:
        checks, citation = audit_bundle(envelopes, spec, pubkey=args.pubkey,
                                        run_id=args.run_id)
    except ValueError as exc:
        print(f"✖ {exc}")
        return 1
    print(format_report(checks, citation, len(envelopes)))
    return 1 if any(c.passed is False for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
