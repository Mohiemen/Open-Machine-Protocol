"""Conformance is the bar: omp-validate must agree with every M1 vector."""
import json

import pytest
from omp_tools.specload import load_spec
from omp_tools.validate import validate_envelope

SPEC = load_spec()
VECTOR_FILES = sorted(SPEC.spec_dir.glob("conformance/core/*.ndjson")) + sorted(
    SPEC.spec_dir.glob("profiles/*/conformance/*.ndjson")
)


def vectors():
    for vf in VECTOR_FILES:
        expect_valid = vf.name == "valid.ndjson"
        for i, line in enumerate(vf.read_text(encoding="utf-8").splitlines(), 1):
            row = json.loads(line)
            envelope = row if expect_valid else row["vector"]
            reason = "" if expect_valid else row["_reason"]
            yield pytest.param(
                envelope, expect_valid, reason,
                id=f"{vf.parent.parent.name}/{vf.name}:{i}",
            )


def test_vector_files_found():
    assert len(VECTOR_FILES) >= 6, VECTOR_FILES


@pytest.mark.parametrize("envelope,expect_valid,reason", list(vectors()))
def test_vector(envelope, expect_valid, reason):
    errors = validate_envelope(envelope, SPEC)
    if expect_valid:
        assert not errors, f"valid vector rejected: {errors}"
    else:
        assert errors, f"invalid vector accepted ({reason})"
