# Security Policy

## Why This Matters More Than Usual

OMP gateways sit inside factory OT networks. A vulnerability here is not a defaced website - it is a foothold next to production machinery in facilities that often lack security staff. We treat reports accordingly, and we ask reporters to treat disclosure accordingly.

## Reporting a Vulnerability

**Do not open a public issue.**

- Use GitHub's private vulnerability reporting on this repository ("Report a vulnerability" under the Security tab), or
- Email the address listed on the repository's security tab, encrypted with the published PGP key if the content is sensitive.

Include - affected component (gateway, exporter, adapter, tool, spec), version or commit, reproduction steps or proof of concept, and your assessment of impact. Partial reports are welcome; do not sit on something because the writeup isn't polished.

## What Counts

In scope - anything that breaks the project's security promises:

- Remote code execution or memory unsafety in gateway, exporters, or tools
- Bypass of envelope integrity (checksum or signature forgery, seq manipulation that evades detection)
- Adapter sandbox/isolation escapes
- Dead-letter or buffer handling that lets invalid data export as valid
- Retrofit firmware vulnerabilities (ESP32 OTA, WiFi provisioning)
- Supply-chain issues in our release pipeline
- Specification-level flaws that make conformant implementations insecure (these are the most valuable reports of all)

Out of scope - misconfigured deployments contrary to the hardening guide, physical access attacks on gateways, vulnerabilities in third-party platforms consuming OMP data, and the machines' own controllers (report those to their vendors; we will help coordinate where an adapter is the vector).

## Our Commitments

| | |
|---|---|
| Acknowledgment | Within 72 hours |
| Initial assessment | Within 14 days |
| Fix or mitigation for confirmed critical issues | Target 90 days, faster where factories are exposed |
| Coordinated disclosure | We publish an advisory with credit to the reporter (or anonymity on request) when a fix ships |
| No legal action | Good-faith research under this policy will never be met with legal threats from this project |

Supported versions - the latest minor release of the current major, and the final minor of the previous major for 12 months after a major release.

## For Deployers

Security-relevant operational guidance lives in [docs/security/hardening-guide.md](docs/security/hardening-guide.md) - OT/IT segmentation, TLS configuration, key management, update practice. Subscribe to release notifications; advisories are published through GitHub Security Advisories on this repository.
