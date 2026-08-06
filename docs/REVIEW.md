# Documentation Bundle Review

Review of the OMP documentation bundle (24 markdown files) as imported under `/docs`.
Scope - internal consistency (conflicts), cross-linking, and gaps.

Overall the bundle is unusually coherent: terminology, constitutional principles,
dedup rules, and the verifiability story are told consistently across governance,
spec, guides, and integration docs. The issues below are the exceptions.

---

## 1. Conflicts / Contradictions

> **Status update 2026-07-23**: all items in this section (1.1-1.10) have been
> fixed as recommended. Details retained below for the record.

### 1.1 Checksum format - spec vs README and architecture doc
- `spec/omp-schema-v0.1.md` section 2 defines `checksum` as **"lowercase hex SHA-256"** (example `"a3f1...c9"`), and the quickstart matches (`"9f2a..."`).
- `README.md` (envelope example) and `docs/architecture/system-architecture.md` section 4.1 show `"checksum": "sha256-..."` - a prefixed format the spec does not allow.
- **Fix**: update README and architecture examples to plain lowercase hex.

### 1.2 Telemetry schema fields - architecture doc vs spec
- Architecture doc 4.1 table: telemetry carries `sample_rate`, `values[]` or `stats`.
- Spec 7.5: telemetry carries `mode` (`samples`/`stats`), `samples[]` of `{t, v}` pairs, `stats`; there is no `sample_rate` field.
- **Fix**: the architecture summary predates the spec; align its table with spec 7.5.

### 1.3 process_run field name - `recipe_or_program_ref` vs `program_ref`
- Architecture doc 4.1: `recipe_or_program_ref`.
- Spec 7.3: `program_ref`.
- **Fix**: architecture doc should say `program_ref`.

### 1.4 energy `source` enum incomplete in architecture doc
- Architecture doc: `source` = `native/ct_clamp/estimated`.
- Spec 7.4 adds `submeter`.
- **Fix**: minor, align the architecture table.

### 1.5 "Every message is wrapped in a signed envelope" - README overclaim
- README "How It Works" says every message is *signed*; the spec makes `sig` optional
  (MAY), and the hardening guide requires signing only for compliance-relevant
  deployments. The README's own example omits `sig`.
- **Fix**: say "checksummed (optionally signed)" or similar. The DPP/FAQ docs are
  scrupulous about not overclaiming; the README should match.

### 1.6 Signature input - glossary vs spec
- Glossary: signature is "over the envelope".
- Spec 2: signature is over `gateway_id || machine_id || seq || checksum`.
- **Fix**: glossary wording (glossary itself says the spec wins - but glossary also
  claims *it* wins over casual usage; the normative JSON/spec should win and the
  glossary entry should be corrected).

### 1.7 Retrofit node transport - ESP-NOW appears only in the glossary
- Glossary: retrofit nodes report "over local WiFi **or ESP-NOW**".
- Retrofit guide and architecture doc describe WiFi + local MQTT only.
- **Fix**: either drop ESP-NOW from the glossary or mark it as roadmap.

### 1.8 Dead-letter "file" vs "store"
- Glossary: "written to a local dead-letter file"; spec/gateway docs: "dead-letter
  store" with attached validation errors, queryable via `omp-gateway dead-letters`.
- **Fix**: trivial wording alignment (prefer "store").

### 1.9 Clone instructions - `cd omp` after cloning `Open-Machine-Protocol`
- README, quickstart, first-real-machine, and CONTRIBUTING all do
  `git clone .../Open-Machine-Protocol` followed by `cd omp`.
- **Fix**: `cd Open-Machine-Protocol` (or note the target dir in the clone command).

### 1.10 Quickstart timing framing
- README: "Quickstart in 60 Seconds"; quickstart.md: "15 Minutes". Cosmetic, but
  they describe the same flow. Also `pip install -e ./gateway ./tools` (README)
  vs `pip install -e ./gateway -e ./tools` (quickstart) - only the latter makes
  both packages editable.

## 2. Linking Review

Cross-linking between documents is generally excellent - the getting-started →
guides → integrations → spec chain resolves, and companion references (spec ↔
profile spec, hardening ↔ factory deployment, DPP ↔ platform ingestion) are all
bidirectional. Verified issues:

### 2.1 Broken relative links (target missing from bundle)

> **Status update 2026-07-23**: all links below now resolve - targets were
> created (`writing-a-profile.md`, `reference/`, `translations/`, milestone
> plan), the LICENSE link repointed to the repo root, and the implementation
> directory links (`examples/`, `tools/`) converted to plain code references
> until the implementation exists.

| Source | Link | Note |
|---|---|---|
| `README.md` | `docs/guides/writing-a-profile.md` (x2) | Referenced 3+ times project-wide; does not exist |
| `README.md` | `docs/reference/` | No reference docs in bundle |
| `README.md` | `docs/translations/` | No translations dir |
| `README.md` | `docs/architecture/10-roadmap/milestone-plan.md` | ~~Missing~~ **Resolved 2026-07-23** - created as the living roadmap |
| `README.md` | `LICENSE` | Exists at repo root, not inside the bundle root; broken while the bundle lives under `/docs` |
| `README.md` | `examples/grafana-dashboards/`, `tools/omp-sniff/` | Code dirs - expected to exist in the implementation repo, absent here |
| `CONTRIBUTING.md` | `docs/translations/`, `tools/omp-sniff/` | As above |
| `docs/getting-started/faq.md` | `../translations/` | Missing |

### 2.2 Prose references to documents that don't exist (not hyperlinked, still dangling)

> **Status update 2026-07-23**: resolved - `MAINTAINERS.md` (bootstrap
> version), `rfcs/0000-template.md`, and the ADR directory
> (`06-decisions/README.md`) now exist. Still open: the threat-model doc
> (05-crosscutting), performance-targets doc, 08-operations docs, and all
> normative JSON artifacts (`spec/schemas/`, `spec/conformance/`) - these are
> tracked in the [milestone plan](docs/architecture/10-roadmap/milestone-plan.md).

- `docs/security/hardening-guide.md` → `architecture/05-crosscutting/security-architecture.md` (threat model) - missing.
- `docs/community/code-of-conduct.md` → `MAINTAINERS.md` (twice; conduct contacts live there) - missing. **This one matters: the CoC currently has no reachable reporting contact.**
- `docs/community/rfc-process.md` → `rfcs/0000-template.md` - missing (the template is inlined in the doc, so recoverable).
- Glossary + rfc-process → `docs/architecture/06-decisions/` (ADR home) - missing.
- `docs/guides/factory-deployment.md` → "the performance targets doc" and "08-operations territory in the architecture docs" - neither exists.
- `spec/omp-schema-v0.1.md` → `spec/schemas/core/*.json` declared **normative**, and `spec/conformance/` declared "the executable definition" of validation - neither present. The prose spec is currently the only artifact, while stating it is not the normative one.
- `spec/profiles/PROFILE-SPEC.md` → `spec/profiles/textile-dyeing/` directory layout (profile.json, events.json, etc.) - only the prose worked example exists.
- `docs/integrations/platform-ingestion.md` → `spec/conformance/consumer/` and `examples/platform-ingest-reference/` - missing.

### 2.3 Structural note

The bundle is a full repo skeleton (README, CONTRIBUTING, GOVERNANCE, SECURITY at
root, plus `spec/` and its own `docs/`). Placed under `/docs`, this produces a
`docs/docs/...` nesting. Internal relative links all assume the bundle root is the
repo root - if these files are later promoted to the actual repo root, every
internal link resolves as authored (only the items in 2.1/2.2 remain broken).
Recommendation: promote the bundle contents to the repo root rather than keeping
them nested, when ready.

## 3. Gaps (content that is referenced or implied but absent)

Ordered by how hard the absence bites:

1. ~~**Writing a Profile guide**~~ - **Resolved 2026-07-23**: authored as the
   how-to companion to PROFILE-SPEC (`docs/guides/writing-a-profile.md`).
2. ~~**MAINTAINERS.md**~~ - **Resolved 2026-07-23**: bootstrap version created
   naming the founder/BDFL; independent conduct contact noted as a tracked
   bootstrap task.
3. ~~**Normative JSON Schemas + conformance vectors**~~ - **Resolved
   2026-07-23**: `spec/schemas/core/` (6 JSON Schemas, draft 2020-12),
   `spec/conformance/` (22 core vectors with computed RFC 8785 checksums +
   consumer cases), and machine-readable profile packages for generic,
   textile-dyeing, and textile-sewing with their own vectors, plus
   `spec/profiles/_template/`. All vectors execute green against the schemas.
   Full consumer NDJSON suites follow with the M2 reference consumer.
4. ~~**Security architecture / threat model**~~ - **Resolved 2026-07-23**:
   authored at `docs/architecture/05-crosscutting/security-architecture.md`
   (assets, trust boundaries, threat actors, attack paths, design-property
   mapping, explicit non-goals); hardening guide companion reference now a
   working link.
5. ~~**Milestone plan / roadmap** (`10-roadmap/milestone-plan.md`)~~ -
   **Resolved 2026-07-23**: created as a living roadmap consolidating the
   scattered roadmap content (architecture doc sections 8/9, README Status,
   vision doc section 7), with a mandatory keep-current rule.
6. **Reference documentation** (`docs/reference/`) - **Partially resolved
   2026-07-23**: scaffold created with a planned-pages index and interim
   pointers; the actual reference pages land with the v0.1 implementation.
7. ~~**Translations** (`docs/translations/`)~~ - **Resolved 2026-07-23**:
   scaffold created with priority order, layout convention, and status table.
8. ~~**RFC template file + rfcs/ directory**~~ - **Resolved 2026-07-23**:
   `rfcs/0000-template.md` created from the inline template.
9. ~~**ADR directory** (`06-decisions/`)~~ - **Resolved 2026-07-23**: created
   with index and ADR format. Remaining architecture numbering (01-03, 05,
   07-09) stays absent until those docs are written - tracked in the milestone
   plan.
10. ~~**textile-sewing profile documentation**~~ - **Resolved 2026-07-23**:
    authored at `spec/profiles/textile-sewing/PROFILE.md` (classes, events,
    deliberate no-phases decision, telemetry, quantities, Bangla glossary,
    conformance vector descriptions). Marked Draft pending its RFC and
    working group per GOVERNANCE 6.2; machine-readable JSON artifacts remain
    an M1 item.
11. **Governance/contact details** - GOVERNANCE names no actual core maintainers
    and SECURITY.md defers to "the address listed on the repository's security
    tab"; fine pre-launch, but worth an explicit "bootstrap status" note.
12. **Operator identity, quality/inspection schema** - the spec's own section 10
    flags these as open; they are tracked in architecture doc section 9 too.
    Consistent, no action - listed here for completeness.

## 4. Smaller observations

- FAQ answer "GOVERNANCE.md section 2" for read-only is correct (constitutional
  principle 2) - verified, not a conflict.
- Sizing guidance is consistent across FAQ ("50-100+ per gateway"), factory
  deployment ("~50 per gateway" baseline), and retrofit ("100+ nodes, WiFi-bound").
- The "honesty ladder" term (retrofit guide, DPP guide) is used twice but never
  defined in the spec it is attributed to; the underlying `source`/`data_source`
  enums do exist. Worth a one-line definition in the glossary.
- Governance BDFL end-condition (5 core maintainers from 3 orgs) vs core
  maintainer target (3-7 from 2+ orgs) - compatible, not conflicting, but the
  asymmetry is easy to misread; a cross-reference would help.
