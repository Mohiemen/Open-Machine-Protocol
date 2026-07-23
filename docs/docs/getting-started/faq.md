# Frequently Asked Questions

| | |
|---|---|
| **Status** | Living document |
| **Location** | docs/getting-started/faq.md |

## About the Project

**Is this a real standard or one company's project?**
It is an openly governed specification under Apache 2.0 with published, binding governance - including the rules that prevent any company (explicitly including the platforms that fund work on it) from buying control. Read [GOVERNANCE.md](../../GOVERNANCE.md); holding us to it is encouraged.

**Why not just use OPC UA / MTConnect / Sparkplug?**
Short answer - OMP bridges to them and targets the machines they never reached (legacy, serial, and dumb equipment, which is most of the world's installed base). Long answer with a comparison table - [Positioning](../architecture/00-overview/positioning.md).

**Can OMP control my machines? Can I add that?**
No, and no. Read-only is constitutional (GOVERNANCE.md section 2) and unamendable. PRs adding control paths are closed regardless of merit. This is a feature - it is why factories, insurers, and safety officers can approve OMP without a controls review.

**What does "verifiable" actually mean here?**
That completeness (sequence numbers), integrity (checksums), and origin (signatures) of the data are mechanically checkable against a public spec. It does NOT mean the sensors were calibrated or that data can't be mislabeled at configuration time - the honest boundary is documented in the [DPP Evidence Chain](../integrations/dpp-evidence-chain.md), section 5.

## Getting Started

**What's the minimum hardware to try it?**
Nothing - the [Quickstart](quickstart.md) runs entirely simulated on a laptop. For a real machine, a Raspberry Pi 4 and either a USB-RS485 adapter (~$10) or an ESP32 retrofit kit (~$15 in parts).

**My machine brand isn't in the adapters list.**
Check whether it speaks Modbus (then `generic-modbus` covers it with a YAML file, no code) or prints serial lines (`generic-serial`). If neither - a [protocol capture](../../CONTRIBUTING.md) is the most valuable thing you can contribute, and collective decoding in the issues genuinely works.

**Does this need internet or a cloud account?**
No. Everything runs on your premises. The gateway exports to wherever YOU configure - which can be a laptop on the same desk. Nothing phones home; that's constitutional too.

**How many machines per gateway?**
Practically, 50 to 100+ per Pi-class gateway; the real constraints are serial port count and WiFi capacity, not compute. Sizing table in [Factory Deployment](../guides/factory-deployment.md).

## Data and Integration

**Who owns the data?**
The factory that runs the gateway. Full stop, constitutionally. Platforms consuming it operate under whatever agreement the factory makes with them - that's between them, and outside OMP's scope by design.

**Can I use OMP data for EU Digital Product Passports?**
That's a core use case - OMP evidence upgrades process claims from self-declared to machine-attested, with a defined citation format and audit procedure. Start at the [DPP Evidence Chain](../integrations/dpp-evidence-chain.md), including its careful section on what is NOT proven.

**We already have SCADA / an MES. Does OMP conflict?**
No - OMP typically feeds them (OPC UA exporter, or your MES ingests the MQTT stream) and covers the machines they never reached. The common pattern is OMP for the long tail, existing systems unchanged.

**Is my production data exposed to the project or other users?**
No. There is no central anything. The project never sees your data unless you paste it into an issue - and scrub captures before you do (CONTRIBUTING has guidance).

## Contributing and Legal

**Is reverse-engineering machine protocols legal?**
Interoperability-purpose reverse engineering of equipment you lawfully operate is protected or tolerated in many jurisdictions, and the project's [method guide](../guides/reverse-engineering-protocols.md) keeps contributions inside the most consistently protected practices - with hard bright lines (no firmware extraction, no NDA material, no defeating protection measures). It's a 10-minute read; do it before capturing.

**I'm a textile/mechanical/production engineer, not a programmer. Can I contribute?**
You may be the most valuable contributor type - profiles require industry practitioners by rule, protocol captures need machine access more than code, and deployment reports need factories. See the ranked list in [CONTRIBUTING.md](../../CONTRIBUTING.md).

**Can I build a commercial product on OMP?**
Yes, that's the intent - Apache 2.0, no strings. Sell gateways, integration services, platforms, hosted analytics, whatever. The only things you can't buy are the spec itself and the community's neutrality.

**Why is documentation being translated to Bangla first?**
Because the project's first target users are on factory floors in Bangladesh, and a quickstart an engineer can read converts directly into deployments and contributors. Other manufacturing-country languages (Vietnamese, Hindi, Turkish, Bahasa) are equally welcome - see [translations](../translations/).

## Troubleshooting

**Where do I ask questions?**
GitHub Discussions for anything - design questions, "is this normal", identification-by-photo of mystery controller ports. Issues for bugs and concrete proposals. Include your OS, versions, and the exact command; annotated detail gets faster answers than politeness.

**Something's broken and I think it might be a security issue.**
Do not open a public issue - use the private reporting channel in [SECURITY.md](../../SECURITY.md). When unsure whether it's security-relevant, treat it as if it is.
