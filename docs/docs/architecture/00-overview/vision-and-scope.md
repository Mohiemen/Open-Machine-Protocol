# Vision and Scope

| | |
|---|---|
| **Status** | Draft |
| **Owner** | M A Mohiemen Tanim |
| **Last updated** | July 2026 |
| **Location** | docs/architecture/00-overview/vision-and-scope.md |

---

## 1. The Problem

Industrial machines generate valuable operational data every second they run. Almost none of it is usable.

- **Proprietary lock-in.** Every machine maker speaks its own protocol. Juki, Brother, Sedo Treepoint, Fanuc, Siemens - each requires separate reverse engineering or licensed middleware. A factory with six brands needs six integrations.
- **Legacy silence.** The majority of machines running in factories across Bangladesh, Vietnam, India, Turkey, and beyond have no digital output at all. They are mechanically excellent and digitally mute.
- **Closed IoT platforms.** Commercial machine-monitoring platforms exist, but they are expensive, cloud-dependent, and keep the factory's own data inside a vendor's walled garden. Small and mid-sized manufacturers, the majority of global manufacturing, are priced out entirely.
- **Unverifiable claims.** Regulations like the EU Digital Product Passport increasingly demand evidence of how goods were made. Today that evidence is mostly self-declared spreadsheets. There is no open, auditable standard connecting a claim to the machine that produced the data.

The result - factories fly blind, integrators rebuild the same drivers endlessly, and compliance rests on trust instead of proof.

## 2. The Vision

**What OBD-II did for cars, OMP does for industrial machines.**

Open Machine Protocol (OMP) is an open-source driver layer and data standard that turns any industrial machine, networked or dumb, modern or 30 years old, into a source of standardized, verifiable operational data.

A world where OMP succeeds looks like this:

- A factory engineer in Gazipur plugs a $15 retrofit node onto a 1998 sewing machine and it streams conformant data within an hour.
- A platform developer writes one ingestion module and instantly supports every machine family the community has ever written an adapter for.
- An auditor verifies a Digital Product Passport claim against machine-signed event records conforming to a public specification, not against a vendor's black box.
- A student in Dhaka reads the protocol documentation in Bangla and contributes adapter number 61.

## 3. Mission

Build and govern, as a community, three things:

1. **A specification** - a domain-neutral core data schema plus industry Domain Profiles, versioned and openly governed.
2. **An implementation** - an edge gateway, protocol adapters, and retrofit hardware designs that emit conformant data from real machines.
3. **An ecosystem** - tooling, conformance testing, and documentation that make contributing a new adapter or profile a weekend project, not a research program.

## 4. Guiding Principles

1. **Spec first, code second.** The schemas are the product. Implementations are replaceable.
2. **Read-only at the edge.** OMP observes machines and never commands them. Safety and trust by construction.
3. **Domain-neutral core, domain-rich profiles.** The core knows nothing about stitches, molds, or spindles. Industry semantics live in profiles.
4. **Vendor and platform neutrality.** No company's fields in the core. Commercial platforms compete on what they build above OMP, never by controlling it.
5. **Offline first, low-resource first.** Designed for factories with unstable power, unreliable networks, and Pi-class budgets.
6. **Verifiable at source.** Sequence numbers, checksums, and gateway signatures make data lineage provable, which is what elevates downstream compliance claims from self-declared to machine-attested.
7. **Accessible in the languages of manufacturing.** Documentation in Bangla and other manufacturing-country languages is a first-class deliverable, not an afterthought.

## 5. Scope

### 5.1 In scope

- Core data schemas - machine identity, events, process runs, energy, telemetry
- Domain Profile mechanism and reference profiles (textile-sewing, textile-dyeing, generic at launch; machining, plastics, packaging, utilities on the roadmap)
- Edge gateway runtime - adapter hosting, validation, buffering, replay, signing, export
- Protocol adapters - generic-modbus, generic-serial, opcua-client, and vendor-specific families
- Retrofit hardware designs and firmware for machines with no digital output
- Exporters - MQTT, REST, OPC UA, CSV
- Conformance tooling, simulators, and protocol capture helpers
- Reference deployment topologies for real factory environments

### 5.2 Out of scope, permanently

- **Machine control.** OMP will never write to, command, or actuate machines. This is a constitutional constraint, not a roadmap gap.
- **Cloud services.** OMP defines no hosted service, no accounts, no telemetry back to the project. Everything runs on the factory's own infrastructure.
- **Analytics, dashboards, planning, compliance logic.** These belong to the platforms above OMP. The project ships example dashboards for demonstration only.
- **Data ownership claims.** Data produced by OMP belongs to the factory that runs it. Full stop.

### 5.3 Out of scope for now

- Non-industrial machinery (agricultural, medical, consumer)
- Formal certification programs beyond conformance testing
- Wireless mesh coordination between gateways

## 6. Target Users

| User | What OMP gives them |
|---|---|
| **Factory owners and engineers** (primary) | Machine visibility without vendor lock-in or cloud fees |
| **Platform builders** (Intelactory-class factory OS, MES, ERP, CMMS) | One integration surface for every machine, plus auditable data lineage for DPP-class compliance |
| **System integrators** | Reusable adapters instead of one-off drivers per project |
| **Adapter and profile authors** | A clear contract, tooling, and a community that ships their work to thousands of factories |
| **Auditors and regulators** | A public specification against which manufacturing evidence can be verified |

## 7. What Success Looks Like

- **v0.1** - one real machine and one Modbus PLC streaming conformant, signed data end to end; spec published with conformance vectors.
- **Year 1** - 10+ community adapters, 3+ domain profiles in production use, first factory running 50+ machines on OMP, first platform citing OMP envelopes in a Digital Product Passport.
- **Year 3** - OMP conformance appears in machine procurement requirements; machine makers ship OMP-native output because customers ask for it. That is the OBD-II moment.

## 8. What OMP Is Not

- Not a competitor to OPC UA or MTConnect - OMP bridges to them and targets the long tail of machines they never reached.
- Not an IoT platform - no cloud, no dashboard product, no subscription.
- Not owned by any company - platforms like Intelactory build on OMP as its best-integrated consumers, under the same rules as everyone else.

## 9. Non-Negotiables

If a future decision would violate any of these, the decision is wrong:

1. The specification remains open and royalty-free (Apache 2.0).
2. The edge remains read-only.
3. The core remains vendor-neutral, with extensions namespaced.
4. Factories own their data.
5. Governance remains multi-stakeholder with no single-vendor veto.
