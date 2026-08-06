# The OMP RFC Process

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/community/rfc-process.md |
| **Authority** | GOVERNANCE.md section 5 |
| **Last updated** | July 2026 |

---

## 1. When You Need an RFC

An RFC (Request for Comments) is required for changes where semantics outlive code:

- Any change to core schemas or the envelope
- Creating a new profile, or breaking changes to an existing one
- Changes to conformance requirements
- Amendments to GOVERNANCE.md

Everything else - implementation, adapters, additive profile releases, docs, tools - is a normal PR. When unsure, ask in Discussions; a maintainer will tell you in a day, which beats writing an unnecessary RFC or having a PR bounced for lacking one.

## 2. The Lifecycle

```
Idea ─▶ Pre-discussion ─▶ Draft PR ─▶ Comment window ─▶ Revision ─▶ Decision ─▶ ADR + Implementation
          (optional,        (rfcs/           (14 or 28 days)                (accept /
           Discussions)      NNNN-title.md)                                  reject / defer)
```

1. **Pre-discussion (optional but wise).** Float the idea in GitHub Discussions. Ten minutes of "has this been tried" saves ten hours of drafting.
2. **Draft.** Copy `rfcs/0000-template.md` to `rfcs/NNNN-short-title.md` (next free number) and open a PR. The PR thread is the discussion venue.
3. **Comment window.** Minimum 14 days from PR opening; 28 days for breaking changes and governance amendments. The window restarts only if the proposal changes fundamentally, not for ordinary revisions.
4. **Revision.** The author incorporates feedback or explicitly rejects it with reasons in the RFC's "Unresolved and rejected alternatives" section. Silence toward a raised objection is grounds for deferral.
5. **Decision.** Core maintainers (BDFL during bootstrap, per GOVERNANCE.md 4.5) record one of:
   - **Accept** - merged; becomes an ADR in `docs/architecture/06-decisions/`; implementation may begin.
   - **Reject** - closed with written rationale; the document is kept, because rejected RFCs are how the project remembers why not.
   - **Defer** - valid but not now; parked with the conditions that would revive it.
6. **Implementation.** Schema changes and their conformance vectors land in the same release. An accepted RFC with no implementation after 6 months reverts to deferred.

## 3. The Template

```markdown
# RFC NNNN - Title

- Status: Draft | Accepted | Rejected | Deferred
- Author(s):
- Comment window ends:
- Affects: core | profile:{name} | conformance | governance

## Summary
One paragraph. A reader should know what changes and for whom.

## Motivation
The problem, with real examples. RFCs that begin from an abstract
nicety rather than an observed need are usually deferred.

## Design
The actual change, precisely. Schema diffs, new field tables,
vocabulary additions. Follow the field-table format of the core spec.

## Compatibility and migration
Additive or breaking? What must consumers, gateways, and adapters
change? For breaking changes, the migration guide outline is
mandatory here, not later.

## Alternatives considered
What else was possible and why not. This section is what makes the
eventual ADR valuable.

## Unresolved questions and rejected feedback
Kept current during the comment window.
```

## 4. Norms

- **Author neutrality is not required; reviewer effort is.** Substantive objections engage with the design. "I don't like it" carries no weight; "this breaks dedup for consumers because..." carries a lot.
- **Practitioner voices are weighted.** On profile RFCs, comments from people who run the machines in question count for more than architectural taste.
- **Small RFCs are good RFCs.** Bundle-everything proposals get asked to split.
- **Non-English participation is welcome.** Comments in Bangla or other languages will be translated by maintainers; ideas matter, polish doesn't.
- **Timeboxes are real.** A decision follows the window's close within 14 days. Proposals do not rot in review; if maintainers are overloaded, the decision is an honest defer, on the record.
