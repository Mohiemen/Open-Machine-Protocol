# Contributing to the Open Machine Protocol

Thank you for being here. OMP only works as a commons - every adapter, profile, capture, translation, and deployment report extends the project's reach into machines and factories the maintainers will never personally touch.

This document covers the mechanics. For why the project exists and how decisions are made, read [Vision and Scope](docs/architecture/00-overview/vision-and-scope.md) and [GOVERNANCE.md](GOVERNANCE.md) first - they are short and they will save you time.

---

## Ways to Contribute, Ranked by Impact

### 1. Adapters (highest impact)

An adapter for a machine family we don't cover extends OMP to every factory running those machines, forever.

- Start with [Writing an Adapter](docs/guides/writing-an-adapter.md) and copy `adapters/_template/`.
- Target - from "I have access to this machine" to merged PR in four weekends. If the guide makes that impossible, that's a bug in the guide; tell us.
- Acceptance requires (see GOVERNANCE.md 6.1) - a named maintainer (you), passing conformance vectors, documented configuration, and a protocol documentation section.
- Reverse-engineering a protocol? Follow [the legal hygiene guide](docs/guides/reverse-engineering-protocols.md) BEFORE you start - interoperability purpose, no vendor firmware copies, documented clean-room method. This protects you as much as the project.

### 2. Profiles

A profile brings an entire industry into OMP. Requires an RFC and at least 2 practitioners from that industry in the working group - see the [Profile Specification](spec/profiles/PROFILE-SPEC.md) and its authoring checklist. If you're a domain expert without a coding background, you are the scarce resource here; we'll pair you with implementers.

### 3. Protocol captures (no coding required)

Have access to a machine we don't support but can't write the adapter yourself? Run `omp-sniff` (in `tools/`) while the machine operates, describe what the machine was doing at each stage, and open an issue with the capture attached. A capture with good annotations is 60% of an adapter. This is the single most valuable non-code contribution.

### 4. Deployment reports

Running OMP in a real factory? A short write-up - machine mix, network conditions, what broke, what surprised you - is gold. Failures are more valuable than successes. Open an issue with the `deployment-report` label.

### 5. Translations

A Bangla, Vietnamese, Hindi, Turkish, or Bahasa quickstart converts real factory engineers into users. Priority order - getting-started first, guides second, reference last. See [docs/translations/](docs/translations/).

### 6. Docs, bugs, tests

Standard but essential. Typos to test coverage, all welcome. Issues labeled `good first issue` are genuinely scoped for a first contribution.

---

## Development Setup

```bash
git clone https://github.com/Mohiemen/Open-Machine-Protocol
cd Open-Machine-Protocol
python -m venv .venv && source .venv/bin/activate
pip install -e "./gateway[dev]" -e "./tools[dev]"

# Verify your environment
pytest gateway/ tools/
omp-simulate --profile generic --machines 2 | omp-validate
```

Python 3.11+. No hardware is needed for most work - `omp-simulate` generates realistic machine data for every shipped profile.

For retrofit firmware - PlatformIO, ESP32 toolchain, see `retrofit/*/docs/`.

## Pull Request Process

1. **Open an issue first** for anything non-trivial, so effort isn't wasted on directions the maintainers can't merge. Exceptions - typos, small doc fixes, test additions.
2. Branch from `main`, one logical change per PR.
3. **Conformance is the bar.** Schema-touching changes must update conformance vectors in the same PR. Adapter PRs must pass `omp-validate` against their emitted output in CI.
4. Write commit messages that explain why, not just what.
5. CI must be green - lint (`ruff`), types (`mypy` on gateway core), tests, conformance.
6. Review - one maintainer approval for implementation code, per GOVERNANCE.md for anything touching the spec. Lazy consensus applies - if a maintainer hasn't responded in 72 hours, ping the thread.
7. Expect review to focus on contracts and vocabularies more than style. Style is automated; semantics are forever.

## What Requires an RFC (not just a PR)

- Any change to core schemas or the envelope
- New profiles or breaking profile changes
- Conformance requirement changes

Process in [docs/community/rfc-process.md](docs/community/rfc-process.md). Everything else is a normal PR.

## Non-Negotiables for All Contributions

These come from the project's constitutional principles and are not open to negotiation in review threads:

1. **No control paths.** Code that writes to, commands, or actuates machines will not be merged, regardless of usefulness.
2. **No vendor or platform fields in core or profiles.** Platform enrichment goes in `x-*` extensions, documented outside this repo.
3. **No phone-home.** Nothing in this codebase contacts any server the operator didn't configure.
4. **No copied vendor firmware or licensed documentation** in reverse-engineered adapters.
5. **Apache 2.0 in, Apache 2.0 out.** By contributing, you license your contribution under Apache 2.0. No CLA beyond the standard [DCO](https://developercertificate.org/) sign-off (`git commit -s`).

## Becoming a Maintainer

Sustained quality contributions to an area (typically 3+ merged PRs and demonstrated review judgment) can lead existing maintainers of that area to offer merge rights. Adapter authors normally become their adapter's maintainer at merge. See GOVERNANCE.md section 4.

## Code of Conduct

We follow the [Contributor Covenant](docs/community/code-of-conduct.md). The short version - the factory floor is a diverse place; so is this project. Technical disagreement is welcome, disrespect is not. Enforcement contacts are listed in the CoC and are separate from technical decision-making.

## Security Issues

Do NOT open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md) for the private reporting channel. Gateway and exporter vulnerabilities affect factory networks; we take them seriously and credit reporters.

## Questions

- GitHub Discussions for design questions and "how do I"
- Issues for bugs and concrete proposals
- Matrix/Discord (links in README) for real-time chat

If you're unsure where something goes, Discussions is always safe.

---

*The target contributor for this project is not a Silicon Valley engineer with a lab. It's an engineer in Dhaka, Ho Chi Minh City, or Tiruppur with access to real machines and an afternoon a week. If any part of contributing feels harder than it needs to be for that person, that's a bug - report it.*
