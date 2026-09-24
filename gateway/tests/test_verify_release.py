"""omp-gateway verify-release - Hardening Guide s6 [Required].

Every vector under fixtures/release/ was produced by the real minisign 0.11,
so these tests check that we interoperate with the tool the guide names,
rather than that we agree with ourselves. The negative cases matter more
than the positive one: a verifier that says yes to everything passes the
happy path too.
"""
import io
import shutil
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
from omp.cli import main as cli_main
from omp.core import release as rel

FX = Path(__file__).parent / "fixtures" / "release"
ARTIFACT = FX / "omp-gateway-0.1.0.tar.gz"


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli_main(list(argv))
    return code, out.getvalue() + err.getvalue()


# -- the format, against real minisign output ----------------------------
def test_verifies_a_real_minisign_signature():
    pub = rel.parse_public_key((FX / "release.pub").read_text())
    sig = rel.parse_signature((FX / "omp-gateway-0.1.0.tar.gz.minisig").read_text())
    assert rel.verify_artifact(ARTIFACT, sig, pub) == \
        "OMP 0.1.0 tag v0.1.0 built 2026-09-24"


def test_verifies_the_legacy_non_prehashed_format():
    """minisign -l. Old release lines still use it; refusing to read it would
    read as tampering to an operator."""
    pub = rel.parse_public_key((FX / "release.pub").read_text())
    sig = rel.parse_signature(
        (FX / "omp-gateway-0.1.0.tar.gz.legacy.minisig").read_text())
    assert sig.algorithm == rel.LEGACY
    assert rel.verify_artifact(ARTIFACT, sig, pub) == "OMP 0.1.0 legacy format"


def test_key_id_matches_what_minisign_prints():
    """An operator compares this string by eye against the release notes."""
    pub = rel.parse_public_key((FX / "release.pub").read_text())
    comment = pub.untrusted_comment      # "minisign public key <ID>"
    assert pub.key_id_hex() == comment.split()[-1]


# -- the cases that must fail --------------------------------------------
def test_tampered_artifact_is_rejected(tmp_path):
    bad = tmp_path / ARTIFACT.name
    bad.write_bytes(ARTIFACT.read_bytes() + b"malicious\n")
    pub = rel.parse_public_key((FX / "release.pub").read_text())
    sig = rel.parse_signature((FX / "omp-gateway-0.1.0.tar.gz.minisig").read_text())
    with pytest.raises(rel.VerifyError, match="does not match the file"):
        rel.verify_artifact(bad, sig, pub)


def test_rewritten_trusted_comment_is_rejected():
    """The file signature still verifies here. Only the global signature
    catches it - which is why we check it. minisign -V rejects this same
    vector with "Comment signature verification failed"."""
    pub = rel.parse_public_key((FX / "release.pub").read_text())
    sig = rel.parse_signature((FX / "rewritten-comment.minisig").read_text())
    assert "9.9.9" in sig.trusted_comment          # the lie is in there
    with pytest.raises(rel.VerifyError, match="trusted comment is not"):
        rel.verify_artifact(ARTIFACT, sig, pub)


def test_signature_from_another_key_is_rejected_by_key_id():
    pub = rel.parse_public_key((FX / "attacker.pub").read_text())
    sig = rel.parse_signature((FX / "omp-gateway-0.1.0.tar.gz.minisig").read_text())
    with pytest.raises(rel.VerifyError, match="different key"):
        rel.verify_artifact(ARTIFACT, sig, pub)


@pytest.mark.parametrize("text,match", [
    ("", "empty"),
    ("untrusted comment: only a comment\n", "no key"),
    ("untrusted comment: x\nnot base64!!\n", "base64"),
    ("untrusted comment: x\n" + "QUJD\n", "expected 42"),
])
def test_malformed_public_keys_are_refused(text, match):
    with pytest.raises(rel.VerifyError, match=match):
        rel.parse_public_key(text)


def test_truncated_signature_file_is_refused():
    lines = (FX / "omp-gateway-0.1.0.tar.gz.minisig").read_text().splitlines()
    with pytest.raises(rel.VerifyError, match="expected 4"):
        rel.parse_signature("\n".join(lines[:2]))


# -- checksums ------------------------------------------------------------
def test_checksum_file_parsing_and_matching():
    sums = rel.parse_checksums((FX / "SHA256SUMS").read_text())
    assert rel.verify_checksum(ARTIFACT, sums) == rel.sha256_file(ARTIFACT)


def test_checksum_mismatch_is_reported(tmp_path):
    bad = tmp_path / ARTIFACT.name
    bad.write_bytes(b"different content")
    sums = rel.parse_checksums((FX / "SHA256SUMS").read_text())
    with pytest.raises(rel.VerifyError, match="SHA-256 mismatch"):
        rel.verify_checksum(bad, sums)


@pytest.mark.parametrize("text", ["", "not a checksum line\n", "abc  f\n"])
def test_malformed_checksum_files_are_refused(text):
    with pytest.raises(rel.VerifyError):
        rel.parse_checksums(text)


# -- CLI ------------------------------------------------------------------
def test_cli_verifies_and_reports_the_trusted_comment():
    code, out = run_cli("verify-release", str(ARTIFACT),
                        "--pubkey", str(FX / "release.pub"))
    assert code == 0
    assert "verified" in out and "tag v0.1.0" in out
    assert rel.sha256_file(ARTIFACT) in out


def test_cli_finds_the_sibling_minisig_by_default():
    code, _ = run_cli("verify-release", str(ARTIFACT),
                      "--pubkey", str(FX / "release.pub"))
    assert code == 0


def test_cli_without_a_pinned_key_refuses_rather_than_passing(tmp_path):
    """The whole point of s6. No key must never look like a pass."""
    assert not rel.PINNED_KEY.exists(), (
        "a release key is now pinned - update this test and the roadmap")
    code, out = run_cli("verify-release", str(ARTIFACT))
    assert code == 1
    assert "pins no release key" in out
    assert "INDEPENDENT of the artifact" in out


def test_cli_missing_signature_file_refuses(tmp_path):
    lonely = tmp_path / "omp-gateway-0.1.0.tar.gz"
    shutil.copy(ARTIFACT, lonely)
    code, out = run_cli("verify-release", str(lonely),
                        "--pubkey", str(FX / "release.pub"))
    assert code == 1 and "no signature file" in out


def test_cli_rejects_the_rewritten_comment_vector():
    code, out = run_cli("verify-release", str(ARTIFACT),
                        "--signature", str(FX / "rewritten-comment.minisig"),
                        "--pubkey", str(FX / "release.pub"))
    assert code == 1 and "trusted comment" in out
    assert "9.9.9" not in out, "never echo an unverified comment as fact"


def test_cli_missing_artifact_is_an_error():
    code, out = run_cli("verify-release", "/nonexistent/thing.tar.gz",
                        "--pubkey", str(FX / "release.pub"))
    assert code == 1 and "no such file" in out


def test_cli_signed_checksum_file_is_reported_as_signed():
    code, out = run_cli("verify-release", str(ARTIFACT),
                        "--pubkey", str(FX / "release.pub"),
                        "--checksums", str(FX / "SHA256SUMS"))
    assert code == 0 and "the checksum file is signed" in out


def test_cli_unsigned_checksum_file_is_called_out(tmp_path):
    """A SHA256SUMS anyone could have written adds nothing, and saying
    'checksums OK' without that caveat is how people end up trusting it."""
    art = tmp_path / ARTIFACT.name
    shutil.copy(ARTIFACT, art)
    shutil.copy(FX / "omp-gateway-0.1.0.tar.gz.minisig",
                tmp_path / (ARTIFACT.name + ".minisig"))
    sums = tmp_path / "SHA256SUMS"
    shutil.copy(FX / "SHA256SUMS", sums)          # no .minisig beside it
    code, out = run_cli("verify-release", str(art),
                        "--pubkey", str(FX / "release.pub"),
                        "--checksums", str(sums))
    assert code == 0
    assert "UNSIGNED" in out and "adds no" in out


def test_cli_checksum_mismatch_fails_even_when_the_signature_passed(tmp_path):
    art = tmp_path / ARTIFACT.name
    shutil.copy(ARTIFACT, art)
    shutil.copy(FX / "omp-gateway-0.1.0.tar.gz.minisig",
                tmp_path / (ARTIFACT.name + ".minisig"))
    sums = tmp_path / "SHA256SUMS"
    sums.write_text("0" * 64 + f"  {ARTIFACT.name}\n")
    code, out = run_cli("verify-release", str(art),
                        "--pubkey", str(FX / "release.pub"),
                        "--checksums", str(sums))
    assert code == 1 and "mismatch" in out
