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


def validate_envelope(envelope: dict, spec) -> list[str]:
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
    return spec.profile_errors(envelope)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omp-validate", description=__doc__)
    parser.add_argument("files", nargs="*", help="NDJSON files (default: stdin)")
    parser.add_argument("--spec-dir", help="path to the spec directory")
    parser.add_argument("--quiet", action="store_true", help="summary line only")
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

    valid = 0
    invalid = 0
    by_schema: Counter[str] = Counter()
    for lineno, line in enumerate(lines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError as exc:
            invalid += 1
            print(f"✖ line {lineno}: not JSON ({exc.msg})")
            continue
        errors = validate_envelope(envelope, spec) if isinstance(envelope, dict) else [
            "not a JSON object"
        ]
        if errors:
            invalid += 1
            if not args.quiet:
                where = (
                    f"seq {envelope['seq']}"
                    if isinstance(envelope, dict) and isinstance(envelope.get("seq"), int)
                    else f"line {lineno}"
                )
                print(f"✖ {where}: {errors[0]}")
        else:
            valid += 1
            by_schema[envelope["schema"]] += 1

    if invalid == 0:
        detail = ", ".join(f"{k} x{v}" for k, v in sorted(by_schema.items()))
        print(f"✔ {valid} messages valid" + (f" (schema: {detail})" if detail else ""))
        return 0
    print(f"{valid} valid, {invalid} invalid (details above)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
