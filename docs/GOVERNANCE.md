# Governance of the Open Machine Protocol

| | |
|---|---|
| **Status** | Draft v0.1 |
| **Applies to** | The OMP specification, profiles, reference implementation, and official repositories |
| **Last updated** | July 2026 |

---

## 1. Purpose

This document defines how decisions are made in OMP, who makes them, and the limits on everyone's power, including the founder's. Its job is to make the project trustworthy to the four groups who must all trust it simultaneously - factories, platform builders, contributors, and eventually machine vendors. It is written down early, before there is anything to fight over, because that is the only time governance can be written calmly.

## 2. Constitutional Principles

These five principles override everything else in this document and in the project. Changing them requires the amendment process in section 10, and some cannot be changed at all.

1. **Open and royalty-free forever.** The specification and reference implementation are Apache 2.0. No future license change may make the spec less open. *(Unamendable)*
2. **Read-only edge.** OMP observes machines and never commands them. *(Unamendable)*
3. **Vendor and platform neutrality.** No company's fields in core or profiles. Extensions are namespaced. No entity may purchase specification control.
4. **Factories own their data.** The project defines no cloud service, no telemetry, no phone-home.
5. **Fork rights are absolute.** Anyone may fork anything at any time. Good governance makes forking unnecessary, not impossible.

## 3. Structure of Authority

OMP separates authority over three areas because they need different levels of ceremony:

| Area | What it covers | Change process |
|---|---|---|
| **Specification** | Core schemas, envelope, profile mechanism, conformance definitions | RFC required, highest bar |
| **Profiles** | Each industry profile's taxonomy and vocabulary | RFC within the profile's working group |
| **Implementation** | Gateway, adapters, tools, docs | Normal PR review by area maintainers |

The rule of thumb - **the spec is sacred, the code is practical.** Semantics that consumers depend on get deliberation; implementation details get velocity.

## 4. Roles

### 4.1 Contributor
Anyone who submits an issue, PR, protocol capture, translation, or deployment report. No approval needed to become one.

### 4.2 Maintainer
Merge rights over a defined area (an adapter, a profile, a tool, gateway subsystems). Granted by existing maintainers of that area based on sustained quality contributions, typically after 3+ merged PRs and demonstrated review judgment. Every adapter must have at least one named maintainer to be accepted; unmaintained adapters are marked and eventually archived, never silently broken.

### 4.3 Core Maintainers
Merge rights over the specification and gateway core. Target size 3 to 7 people from at least 2 unaffiliated organizations once the project matures. Core maintainers are appointed by consensus of existing core maintainers.

### 4.4 Profile Working Groups
Each profile has a working group of maintainers plus practitioners from that industry. Profiles evolve semi-independently under their own RFCs, within constraints set by the core spec.

### 4.5 Founder / BDFL Phase
During bootstrap (pre-1.0), the founder acts as benevolent dictator for the specification to keep early decisions coherent and fast. This is explicitly temporary. The BDFL phase ends at v1.0 of the spec or at 5 core maintainers from 3 organizations, whichever comes first, after which section 5 governs fully. Even during the BDFL phase, the constitutional principles bind the founder, and all spec decisions require a published RFC with a public comment window.

## 5. Decision Making

### 5.1 Default - lazy consensus
Most decisions are made by lazy consensus - a proposal (issue or PR) stands for 72 hours; silence is consent. Any maintainer of the affected area may object and convert it to a discussion.

### 5.2 Specification changes - the RFC process
1. **Draft** - anyone opens an RFC using the template in `docs/community/rfc-process.md`, stating motivation, design, alternatives considered, and migration impact.
2. **Comment window** - minimum 14 days public discussion (28 days for breaking changes).
3. **Revision** - author incorporates or explicitly rejects feedback with reasons.
4. **Decision** - core maintainers (or BDFL during bootstrap) accept, reject, or defer, in writing, with rationale. Accepted RFCs become ADRs.
5. **Implementation** - conformance vectors updated in the same release as the schema change.

### 5.3 Voting - the last resort
If consensus fails among core maintainers after genuine effort, a simple majority vote of core maintainers decides, with the outcome and dissents recorded publicly. Votes are expected to be rare; frequent voting is treated as a governance failure to be examined.

### 5.4 What always requires an RFC
- Any change to core schemas or the envelope
- Creating or breaking-changing a profile
- Conformance requirement changes
- This governance document (see section 10)

## 6. Acceptance Criteria

### 6.1 Adapters
An adapter PR is merged when it has - a named maintainer, passing conformance vectors, documented configuration, a protocol documentation section (including reverse-engineering method where applicable, per the legal hygiene guide), and no network access beyond its machine link.

### 6.2 Profiles
A new profile requires - an RFC, at least 2 practitioners from the target industry in its working group, a machine class taxonomy, an event vocabulary, conformance vectors, and at least one adapter or simulator emitting it.

### 6.3 Vendor-verified tier
Machine vendors may co-maintain the adapter for their equipment and receive a vendor-verified badge. Co-maintenance grants review participation, never exclusive control - community maintainers retain equal merge rights, and fork rights remain absolute.

## 7. Funding and Neutrality

OMP accepts funding (money, hardware, developer time) under public, uniform rules:

1. All funding sources and amounts above a nominal threshold are disclosed publicly.
2. Funding buys gratitude and roadmap input - a funder may propose and prioritize work by staffing it.
3. Funding never buys merge rights, RFC approval, veto power, or specification content.
4. No single organization may employ a majority of core maintainers once the BDFL phase ends. If drift occurs through hiring, the imbalance must be resolved within 6 months by expanding the maintainer group.
5. Platform builders (including Intelactory, the project's expected first integrator) operate under exactly these rules. This clause exists because the project's neutrality is worth more to every platform, including the first one, than any private advantage would be.

## 8. Conflict Resolution

1. **Technical disagreements** - resolved in the area's normal process (PR review, RFC), escalating to core maintainers only when cross-area.
2. **Conduct issues** - handled under the Code of Conduct by its named enforcement contacts, kept separate from technical authority where possible.
3. **Governance disputes** - raised as a public issue tagged `governance`; core maintainers must respond in writing within 14 days.
4. **Irreconcilable direction disputes** - the fork right is the final resolution mechanism, and the project commits to making forks practical - no trademark aggression against good-faith forks that clearly distinguish their naming.

## 9. Transparency Obligations

- All decisions of record (RFC outcomes, votes, maintainer appointments, funding) are public.
- Private channels may be used for security reports, conduct issues, and vendor negotiations only. Outcomes still get public summaries.
- The project publishes a brief state-of-the-project note at least twice a year - releases shipped, maintainer changes, funding received, risks.

## 10. Amending This Document

- Amendments follow the RFC process with a 28-day comment window and require consensus (or failing that, a two-thirds vote) of core maintainers.
- Sections marked *(Unamendable)* in the constitutional principles - open licensing and the read-only edge - may not be amended. A project that wants to change them is a different project and should fork under a different name.

---

*Governance exists so that the people who depend on OMP - a factory in Gazipur, a platform team in another country, a student writing adapter number 61 - can predict how this project will behave when it matters. Hold us to it.*
