<!-- Thanks for contributing. Delete sections that don't apply. -->

## What and why

<!-- What changes, and what problem it solves. Link the issue if there is one. -->

## Type

- [ ] Adapter (new machine family)
- [ ] Profile (new/changed industry vocabulary — needs an RFC first)
- [ ] Gateway / tools / core
- [ ] Docs or translation
- [ ] Deployment report

## Checks

- [ ] CI is green (lint, tests, end-to-end driver)
- [ ] Commits explain *why*, not just what
- [ ] Signed off (`git commit -s`) — [DCO](https://developercertificate.org/)
- [ ] Schema-touching changes update the conformance vectors in this same PR

## Non-negotiables

These come from the constitutional principles and are not negotiable in review
([GOVERNANCE.md](../docs/GOVERNANCE.md)). Confirm your change keeps them:

- [ ] **No control paths** — nothing writes to, commands, or actuates a machine
- [ ] **No vendor or platform fields** in core or profiles (`x-*` extensions only)
- [ ] **No phone-home** — nothing contacts a server the operator didn't configure
- [ ] **No copied vendor firmware or NDA'd documentation**

## For adapters

- [ ] Named maintainer (you): @
- [ ] `PROTOCOL.md` included; reverse-engineered protocols carry the method
      statement from the [legal hygiene guide](../docs/docs/guides/reverse-engineering-protocols.md)
- [ ] `config.schema.json` present
- [ ] Fixtures scrubbed of serial numbers and production data
- [ ] Conformance run passes for every profile in `supported_profiles`

**Soak declaration** — the longest continuous run against real hardware (or a
hardware-faithful simulator), and the known failure modes. Honesty here is a
review criterion, not a formality: *"8 hours, loses connection on power dip,
recovers in under 60 s"* is a perfectly good declaration. *"Replay-tested
only, no hardware"* is also fine — say so.

> 

## For deployment reports

Machine mix, network conditions, what broke, what surprised you. Failures are
more valuable than successes.
