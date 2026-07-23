# Stakeholders

| | |
|---|---|
| **Status** | Draft |
| **Owner** | M A Mohiemen Tanim |
| **Last updated** | July 2026 |
| **Location** | docs/architecture/00-overview/stakeholders.md |

---

## 1. Purpose

This document identifies everyone with a stake in OMP, what each group needs, what they contribute, and what would drive them away. Architecture and governance decisions should be checked against this map - a decision that serves one group while breaking another's core need is a wrong decision.

## 2. Stakeholder Map

```
                 High influence on project
                          ▲
                          │
        Maintainers ●     │     ● Platform builders
                          │        (Intelactory-class)
   Adapter/profile ●      │
        authors           │     ● Anchor factories
                          │        (early deployments)
──────────────────────────┼──────────────────────────▶
  Low direct              │              High direct
  involvement             │              involvement
                          │
   Machine vendors ●      │     ● System integrators
                          │
   Regulators/auditors ●  │     ● Factory engineers
                          │        (end users at scale)
```

## 3. Primary Stakeholders

### 3.1 Factory engineers and owners

The end users OMP ultimately serves. Mostly small and mid-sized manufacturers in Bangladesh, Vietnam, India, Turkey, Indonesia, and similar manufacturing economies.

- **Need** - machine visibility at near-zero cost, no cloud dependency, no vendor lock-in, installable by their own staff, documentation they can read.
- **Contribute** - deployments, bug reports, machine access for adapter development, credibility ("running in real factories").
- **Driven away by** - complexity, English-only docs, anything requiring a control-system engineer, subscription creep, data leaving their premises.
- **Success measure** - time from unboxing to first machine streaming. Target under one day for a competent electrician.

### 3.2 Platform builders

Factory OS, MES, ERP, CMMS, analytics, and DPP platforms that consume OMP data. Intelactory is the reference case and expected first integrator.

- **Need** - stable schemas, semver discipline, one ingestion surface for all machines, verifiable lineage they can cite in compliance documents, extension mechanism that does not require forking.
- **Contribute** - ingestion implementations, real-world schema feedback, funding and developer time, market pull ("works with OMP" as a feature).
- **Driven away by** - breaking changes without migration paths, one competitor controlling the spec, core schemas polluted with another vendor's fields.
- **Governance note** - platform builders get a voice, never a veto. Intelactory operates under the same rules as any other consumer, documented publicly, because the project's neutrality is worth more to every platform (including Intelactory) than any private advantage.

### 3.3 Adapter and profile authors

The community developers who extend OMP's reach - the project lives or dies by them.

- **Need** - a clear plugin contract, conformance tooling that gives fast pass/fail feedback, a template that makes the first adapter a weekend project, credit and maintainer recognition, a documented reverse-engineering process that protects them legally.
- **Contribute** - the adapter and profile library, which IS the network effect.
- **Driven away by** - review queues that sit for months, moving APIs, gatekeeping, unclear legal ground.
- **Success measure** - time from "I have this machine" to merged adapter. Target under four weekends.

### 3.4 Maintainers

The small group with merge rights over core, spec, and gateway.

- **Need** - sustainable workload, funding for CI and test hardware, an RFC process that pushes decisions to the community instead of their inbox.
- **Contribute** - continuity, quality bar, release discipline.
- **Driven away by** - burnout, single-company capture pressure, hostile forks over governance failures.

## 4. Secondary Stakeholders

### 4.1 System integrators

Firms deploying machine connectivity as a service. OMP turns their one-off driver projects into reusable commons, and they turn OMP into installed base.

- **Need** - deployment references, capacity planning tables, something they can bill services on top of.
- **Risk** - some integrators profit from closed one-off work and may resist commoditization. The answer is the same as Linux's - more total service revenue exists on an open base.

### 4.2 Anchor factories

The first 3 to 5 factories running OMP at meaningful scale (50+ machines). Disproportionately important - they generate the case studies, the hard bugs, and the credibility.

- **Need** - white-glove support during pilots, honest handling of failures, recognition.
- **Selection criteria** - mixed machine fleet, unstable-infrastructure realism, management willing to publish results.

### 4.3 Machine vendors

Long-term, the most important conversion target. Short-term, mostly indifferent or defensive.

- **Trajectory** - ignore, then observe, then a progressive vendor ships OMP-native output as a differentiator, then procurement language makes it table stakes. The OBD-II sequence.
- **What we offer them** - a `vendor-verified` adapter tier, co-maintained adapters, and buyer demand data.
- **What we never offer** - spec control in exchange for endorsement.

### 4.4 Regulators and auditors

Consumers of OMP-derived evidence in DPP-class compliance regimes (EU ESPR and successors).

- **Need** - a stable public specification to verify against, cryptographic lineage, versioned conformance definitions.
- **Contribute** - nothing directly, but regulatory citation of open verifiable standards is a massive adoption tailwind.
- **Caution** - the project documents what OMP evidence does and does not prove (see dpp-evidence-chain.md). Overclaiming attestation strength would be the fastest way to lose this audience.

### 4.5 Academic and student contributors

Universities in manufacturing economies (including AUST, BUET-class institutions in Bangladesh) as a contributor pipeline - thesis projects, adapter development, translation work.

- **Need** - well-scoped starter issues, Bangla documentation, mentorship paths.

## 5. Stakeholder Conflicts and Resolutions

| Conflict | Resolution principle |
|---|---|
| Platform builders want fast schema evolution vs factories want stability | Semver + long deprecation windows. Factories win on stability; platforms get additive minor releases. |
| One platform (e.g. Intelactory) funds heavily vs neutrality requirement | Funding buys roadmap input and gratitude, never merge rights or veto. Documented in GOVERNANCE.md. |
| Integrators want billable complexity vs mission wants simplicity | Simplicity wins in core; integrators are pointed at deployment, customization, and scale services. |
| Vendors want control of "their" adapters vs community ownership | Vendor-verified tier gives co-maintenance, not ownership. Community fork rights are absolute. |
| Speed of a small maintainer group vs legitimacy of open process | RFCs for spec changes, maintainer discretion for implementation. The spec is sacred, the code is practical. |

## 6. Communication Channels

| Stakeholder | Primary channel |
|---|---|
| Factory engineers | Docs (translated), video walkthroughs, WhatsApp/Telegram community groups |
| Platform builders | GitHub Discussions, integration guide, release notes |
| Adapter authors | GitHub issues/PRs, Discord/Matrix, conformance CI |
| Anchor factories | Direct support channel during pilot phase |
| Vendors | Direct outreach, industry events, published buyer-demand data |
| Regulators | Published spec, conformance documentation, written correspondence |
