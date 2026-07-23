# Agent Instructions - Open Machine Protocol (OMP)

Guidance for AI coding agents working in this repository.

## What this repository is

OMP is an open-source driver layer and data standard for industrial machines -
"what OBD-II did for cars, OMP does for industrial machines." The repository is
currently **documentation-only**: the specification, governance, and guides live
here; the implementation (gateway, adapters, tools) described in the docs does
not exist in this repo yet.

## Layout

```
LICENSE                 Apache 2.0
README.md               Top-level repo readme
AGENTS.md               This file
docs/                   Imported documentation bundle (a repo-skeleton layout)
├── README.md           Project readme (bundle root)
├── CONTRIBUTING.md     Contribution mechanics
├── GOVERNANCE.md       Decision-making rules, constitutional principles
├── SECURITY.md         Vulnerability reporting policy
├── REVIEW.md           Consistency review: known conflicts, broken links, gaps
├── spec/               Core schema spec + profile spec (prose, v0.1 draft)
└── docs/               Architecture, getting-started, guides, integrations,
                        security, community docs
```

Note the `docs/docs/` nesting: the bundle is a full repo skeleton kept intact so
its internal relative links resolve. If the bundle is ever promoted to the repo
root, links keep working as authored.

## Read before editing

1. **`docs/REVIEW.md`** - the authoritative list of known inconsistencies,
   broken links, and content gaps. Check it before "fixing" something (it may be
   a known issue with a preferred fix) and update it when you resolve an item.
2. **`docs/GOVERNANCE.md`** - five constitutional principles bind all content.
   Never author docs, examples, or code that: add machine control/write paths,
   add vendor- or platform-specific fields to core or profiles (extensions go in
   `x-*` blocks), introduce phone-home/cloud dependencies, or weaken the
   open-licensing terms.
3. **`docs/spec/omp-schema-v0.1.md`** - the source of truth for envelope and
   schema facts. When other docs disagree with it, the spec wins (see REVIEW.md
   section 1 for the known cases).
4. **`docs/docs/architecture/10-roadmap/milestone-plan.md`** - the living
   roadmap. **Mandatory**: any change that completes, adds, reorders, or
   invalidates a roadmap item MUST update this file in the same commit/PR -
   check the item off with a date, bump `Last updated`, and append a changelog
   line. A milestone is not achieved until recorded there.

## Conventions

- **Envelope examples** must match the spec: `checksum` is lowercase hex SHA-256
  (no `sha256-` prefix), `sig` is optional, `seq` starts at 1, `ts` is ISO 8601
  UTC with millisecond precision and `Z` suffix, IDs match
  `^[a-z0-9][a-z0-9-]{2,62}$`.
- **Identifiers** in profiles (event types, phases, channels, classes) match
  `^[a-z][a-z0-9_]*$`.
- **Terminology** follows `docs/docs/architecture/00-overview/glossary.md`
  (adapter, gateway, envelope, profile, dead letter, retrofit node, etc.).
- **Doc front matter**: each doc opens with the small `| | |` status table
  (Status / Location / Audience / Last updated as applicable). Keep the
  `Location` field accurate when moving files.
- **Links**: use relative links; run a relative-link check after moving or
  renaming files. Don't add links to files that don't exist - REVIEW.md
  section 2 tracks the currently known dangling references.
- **RFC-worthy changes**: any change to core schemas, the envelope, profiles,
  or conformance requirements needs an RFC per `docs/docs/community/rfc-process.md` -
  don't make such semantic changes as ordinary edits.
- **Tone**: the docs are written for a factory engineer in Dhaka or Ho Chi Minh
  City with an afternoon a week, not for a lab. Plain language, concrete
  examples, honest about limitations (see the DPP guide's "what is NOT proven"
  section for the house style on honesty).

## Git workflow

- Branch from `main`; one logical change per PR.
- Commit messages explain *why*, not just what.
- Never commit secrets, real factory data, or unscrubbed protocol captures.
