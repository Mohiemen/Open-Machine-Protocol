# RFC 0001 - Pin the Envelope Signature Input Encoding

- Status: Draft
- Author(s): M A Mohiemen Tanim (founder/BDFL, bootstrap phase)
- Comment window ends: 14 days from PR opening (additive clarification, not a breaking change)
- Affects: core

## Summary

Core Schema Specification v0.1 section 2 defines the optional `sig` field as
an "Ed25519 signature over `gateway_id || machine_id || seq || checksum`" but
never defines what `||` means as a byte sequence. Two conformant
implementations can therefore produce signatures neither can verify. This RFC
pins the signature input to a single unambiguous encoding: the four values
rendered as UTF-8 text and joined by `\n` (U+000A).

## Motivation

The gap is not theoretical - it was found by writing the second consumer of
the field. The reference gateway signs
(`gateway/omp/core/keys.py`) and `omp-validate --pubkey` verifies
(`tools/omp_tools/sigverify.py`); both work only because the same author
wrote both and picked the same convention. Anyone implementing OMP signing
from the prose alone today would plausibly choose:

- raw concatenation of UTF-8 bytes with no separator, with `seq` as decimal
  text (`gw-dhaka-f1-01f1-dye-jet02102331a3f1...`)
- the same, with `seq` as 8-byte big-endian binary
- a length-prefixed or delimiter-joined form
- the JSON serialization of the four fields

All four satisfy the prose. Only one can interoperate. Because signatures are
the project's *origin* evidence - the thing a DPP auditor re-runs years later
(DPP Evidence Chain section 4.3) - an ambiguity here is worse than an
ambiguity in a data field: it fails silently at verification time, long after
the data was produced, and the natural reading of a failed verification is
"tampering," not "encoding mismatch."

Separator-free concatenation is additionally *not injective*: the fields have
no fixed widths, so `gateway_id="gw-a"`, `machine_id="b1"` and
`gateway_id="gw-ab"`, `machine_id="1"` produce identical inputs. That is a
real (if narrow) forgery surface, and it argues for a delimiter rather than
merely for documenting whichever encoding shipped first.

## Design

Replace the `sig` row's rule in core spec section 2 with:

> `sig` | string | MAY | Base64 (RFC 4648 standard alphabet, padding
> included) Ed25519 signature. The signed message is the UTF-8 encoding of
> the four envelope values joined by LF (U+000A), in this order and with no
> trailing newline:
>
> ```
> gateway_id LF machine_id LF seq LF checksum
> ```
>
> `seq` is rendered as its shortest decimal representation, without sign,
> leading zeros, or separators. `checksum` is the lowercase hex string
> exactly as it appears in the envelope. The signature is verified against
> the public key registered for `gateway_id` at the envelope's `ts`
> (DPP Evidence Chain section 6).

Add a note after the table:

> The delimiter matters: none of the four values may contain LF
> (`gateway_id` and `machine_id` are constrained by their patterns, `seq` is
> an integer, `checksum` is hex), so this encoding is injective - distinct
> field tuples always produce distinct signed messages.

Worked example, to be added to section 2 and shipped as a conformance
vector:

```
gateway_id: gw-dhaka-f1-01
machine_id: f1-dye-jet02
seq:        102331
checksum:   a3f1...c9

signed message (UTF-8; LF written here as \n):
"gw-dhaka-f1-01\nf1-dye-jet02\n102331\na3f1...c9"

reproducible from a shell:
printf 'gw-dhaka-f1-01\nf1-dye-jet02\n102331\na3f1...c9' | ...
```

### Conformance

Add to `spec/conformance/core/`:

- `signing.md` documenting the construction with a fixed test key, a fixed
  envelope, and the expected base64 signature, so any implementation can
  self-check without contacting another implementation.
- A signed valid vector and an invalid vector whose signature was computed
  over a different encoding (separator-free), which a conformant verifier
  MUST reject.

The existing sig-bearing vector in `core/valid.ndjson` carries a
syntactically valid but unverifiable signature; it stays as a syntax-only
case and the new vectors cover verification.

## Compatibility and migration

**Additive clarification, not a breaking change**, under the reasoning that
the prose never defined a behavior to break:

- `sig` is `MAY`, so no conformant producer is required to have emitted one.
- The only known implementation that signs is this repository's gateway, and
  it already uses the encoding proposed here - so accepting this RFC changes
  no shipped behavior and invalidates no existing data.
- Consumers that never verified signatures are unaffected.
- Any unknown third-party implementation that chose a different encoding
  would have been non-interoperable already; this RFC is what lets them find
  out cheaply, and the conformance vectors above are the mechanism.

Core spec version: fold into `0.1.x` as a clarification, since it pins an
undefined behavior rather than changing a defined one. If a reviewer judges
that any implementation could reasonably have shipped a different encoding in
good faith, the fallback is a `0.2.0` minor with a migration note - the
author's position is that the field's `MAY` status and the absence of any
other known signing implementation make that unnecessary ceremony.

## Alternatives considered

1. **Separator-free UTF-8 concatenation.** Closest to a literal reading of
   `||`, and probably what most implementers would guess first. Rejected
   because it is not injective across variable-length fields (see Motivation)
   - a delimiter costs nothing and removes an ambiguity class entirely.
2. **Sign the canonical `body` bytes directly instead of the checksum.**
   Cleaner in isolation, but it discards the binding to `gateway_id`,
   `machine_id`, and `seq` - a signed body could then be replayed under a
   different machine or sequence number, which is precisely the substitution
   the current construction prevents. Rejected as a security regression.
3. **Sign the full canonical envelope minus `sig`.** Strongest binding, and
   worth considering for a future high-assurance profile, but it makes
   verification depend on canonicalizing the whole envelope (including `ts`
   and `profile`) rather than four short strings, and it changes what the
   field means rather than clarifying it. Out of scope for a clarification;
   noted here as a candidate for a future RFC.
4. **Length-prefixed encoding** (e.g. each field prefixed by its byte
   length). Also injective and delimiter-independent, but harder to
   reproduce by hand or in a shell script during an audit. Rejected in favor
   of the form an auditor can construct with `printf`.
5. **Leave it implementation-defined and register encodings per gateway in
   the key registry.** Rejected - it pushes an interoperability problem into
   every consumer and every audit, in exchange for flexibility nobody asked
   for.

## Unresolved questions and rejected feedback

- Should the signed message include `omp_version` or `profile`, so a
  signature cannot be carried across a spec or profile major version? The
  author's view is no: the checksum already commits to the body's content,
  and adding version fields would make signatures brittle across
  re-serialization. Raised here explicitly so a reviewer can disagree on the
  record.
- Whether to require signatures (not merely `MAY`) for envelopes whose
  `data_source` is `native` and that are cited in DPP claims. That is a
  deployment policy question the Hardening Guide already answers
  operationally ("`signing: required` for any deployment whose data may
  support compliance claims"); making it normative in the core spec is a
  separate proposal.
- Kept current during the comment window.
