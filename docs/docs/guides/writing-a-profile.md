# Writing a Profile

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/guides/writing-a-profile.md |
| **You need** | Deep familiarity with one industry's machines and processes. Coding is optional - the project pairs domain experts with implementers. |
| **Companion** | The [Profile Specification](../../spec/profiles/PROFILE-SPEC.md) is the normative rulebook; this guide is the path through it. Its section 8 (textile-dyeing) is the worked example to keep open while you write. |

A Domain Profile brings an entire industry into OMP - it defines what kinds of
machines exist, what events they produce, what a process run's phases mean, and
what telemetry matters. If you run, maintain, or engineer the machines of an
industry OMP doesn't cover yet, you are the scarce resource this guide exists
for.

A profile is intentionally small: a few focused days of a domain expert's time,
not a research program. If it's taking longer, the profile is overreaching -
see "When in doubt, leave it out" below.

---

## Before You Start

1. **Check the roadmap and open RFCs.** Your industry may already be in
   progress ([milestone plan](../architecture/10-roadmap/milestone-plan.md),
   open RFC PRs). Joining an existing working group beats starting a parallel
   one.
2. **Confirm a profile is the right tool.** A single machine family that fits
   an existing profile's vocabulary needs an *adapter*, not a profile. A few
   missing event types in an existing profile need a minor-version RFC to that
   profile, not a new one.
3. **Find your second practitioner.** Acceptance requires at least 2
   practitioners from the target industry in the working group
   (GOVERNANCE.md 6.2). Post in Discussions early - "forming a working group
   for {industry}" - and recruit while you draft.

## Step 1 - Scope the Domain (one afternoon)

Write three lists, from floor experience, not from catalogs:

- **Machine classes** - the kinds of machines as the floor names them. Closed
  list plus an `other` escape hatch. The dyeing profile has 9; more than ~15
  usually means the scope is two profiles.
- **Events worth recording** - what happens on these machines that anyone
  downstream would care about: quality signals, faults, phase boundaries,
  operator-visible occurrences. Only what machines (or retrofit sensors)
  actually report - "model what machines report, not what managers wish for."
- **The process skeleton** - for batch/job industries, the phases a run moves
  through, chosen so a compliance claim could cite them (temperature curves,
  hold durations, dosing points). Not every industry has phases; a discrete
  cycle industry may need none.

Boundary discipline: derived judgments (efficiency, quality grades, shade
accuracy) live upstream in platforms, never in the profile.

## Step 2 - Open the RFC

Copy `rfcs/0000-template.md`, state motivation and scope boundaries, open the
PR ([RFC process](../community/rfc-process.md)). New profiles get a 14-day
comment window. Practitioner comments are weighted over architectural taste -
by rule.

Don't wait for the RFC to close to continue drafting; the RFC thread will
improve the draft.

## Step 3 - Draft the Vocabulary

Work through the [Profile Specification](../../spec/profiles/PROFILE-SPEC.md)
section 2 artifact by artifact, mirroring the textile-dyeing worked example's
level of detail:

- **Machine classes** - each with a one-line definition a stranger can apply.
- **Event vocabulary** - every event type gets a payload schema, even if empty
  (undocumented payloads are non-conformant). Specialize core types where the
  meaning is domain-specific (as `machine_fault` specializes `error`), never
  redefine them.
- **Phases** - each with a `params` schema carrying what an audit would need.
- **Telemetry channels** - recommended names with UCUM units.
- **Quantities** - recommended names for `process_run.quantities[]`.

Rules that bind you (spec section 3): identifiers match `^[a-z][a-z0-9_]*$`;
no vendor or platform fields, ever; closed vocabularies with `other` +
`detail` beat free text; name from the operator's floor language
(`needle_break`, not `thread_discontinuity_event`), and include a
local-language glossary where relevant (Bangla first for textile profiles).

## Step 4 - Prove It Works

A profile MUST be implementable at acceptance (no speculative profiles):

- **Conformance vectors** - valid cases (a complete run, a run with the
  domain's characteristic mid-process events, an aborted run) and invalid
  cases (unknown phase, missing required payload field, wrong types). These
  are the executable definition of your profile.
- **One emitting implementation** - an adapter, or an `omp-simulate` scenario
  (`--profile {name}`), which is the usual path when no adapter exists yet.
  This is where a paired implementer carries the work if you don't code.

## Step 5 - Acceptance and Stewardship

Run the [authoring checklist](../../spec/profiles/PROFILE-SPEC.md#9-profile-authoring-checklist)
top to bottom, then request decision on the RFC. On acceptance the profile
enters the lifecycle at `active` and your working group owns its evolution -
additive changes are minor releases by normal PR; removals and semantic
changes are major releases requiring a new RFC with migration guidance.

## Traps Seen Elsewhere, Avoided Here

- **The catalog trap** - modeling every machine variant a vendor sells rather
  than the classes a floor distinguishes. Ask "would two different `machine_class`
  values ever change how a consumer interprets the data?" If not, merge them.
- **The wishlist trap** - fields no controller reports, "for the future."
  Anything can be added in a minor release; removal costs a major.
- **The free-text trap** - every free-text field is a future data-cleaning
  project in someone's platform. Enumerate, with `other` + `detail`.
- **The vendor trap** - a vendor's phase codes or register names leaking into
  the vocabulary. Adapters translate vendor reality into profile vocabulary;
  the profile never mentions the vendor.

## If You Get Stuck

Post in Discussions with whatever you have - a half-finished taxonomy from a
person who runs the machines is worth more to this project than a polished
document from someone who doesn't. Maintainers will pair you with implementers
and RFC-shepherd the rest.
