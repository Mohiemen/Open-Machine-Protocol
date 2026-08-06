# Profile Template

Copy this directory to `spec/profiles/{your-profile-name}/` and work through
the [Writing a Profile guide](../../../docs/guides/writing-a-profile.md) with
the [Profile Specification](../PROFILE-SPEC.md) as the rulebook.

- Replace every `{placeholder}`.
- Every event type MUST have a payload schema, even if empty.
- All identifiers match `^[a-z][a-z0-9_]*$`.
- Add `PROFILE.md` (prose - see `textile-sewing/PROFILE.md` for the shape) and
  `conformance/valid.ndjson` + `invalid.ndjson` (generate checksums with
  `spec/conformance/tools/gen_vectors.py`'s helpers).
- Acceptance requires an RFC and 2+ industry practitioners in the working
  group (GOVERNANCE.md 6.2).
