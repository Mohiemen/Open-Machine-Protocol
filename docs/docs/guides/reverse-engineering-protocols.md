# Reverse-Engineering Machine Protocols - Method and Legal Hygiene

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/guides/reverse-engineering-protocols.md |
| **Audience** | Anyone decoding an undocumented machine protocol for an OMP adapter |
| **Read before** | Capturing a single byte |

**This document is community-maintained guidance, not legal advice.** Laws differ by country and change over time. For commercial deployments in uncertain situations, consult a lawyer familiar with your jurisdiction. What follows keeps you inside the practices that interoperability case law and statutes have most consistently protected, and gives the project a documented basis for accepting your work.

---

## 1. The Principles That Protect You

Reverse engineering for **interoperability** - making independently owned equipment work with independently written software - enjoys explicit protection or established tolerance in many jurisdictions (EU Software Directive art. 6, US DMCA interoperability exemptions and case law, and similar provisions elsewhere). That protection is strongest when you can show:

1. **Legitimate access** - you observed a machine you or a cooperating factory lawfully owns and operates.
2. **Interoperability purpose** - the goal is reading the machine's data, not cloning the vendor's product, defeating licensing, or accessing anyone else's systems.
3. **Observation over extraction** - you decoded what the machine says on the wire, rather than copying the vendor's software.
4. **A clean-room record** - contemporaneous documentation showing your knowledge came from observation and analysis.

Everything in this guide operationalizes those four points.

## 2. Bright Lines - The Project Will Not Accept

- **No copied vendor material.** No firmware dumps, no decompiled vendor code, no text from licensed/NDA'd documentation pasted into PROTOCOL.md. Publicly published vendor manuals may be cited and paraphrased; leaked or NDA material may not be used at all, and "I found the internal spec on a forum" is NDA material with extra steps.
- **No circumvention of protection measures.** If a controller encrypts or authenticates its communications specifically to control access, decoding around that is a different legal category from observing a plaintext protocol. Stop and raise it in a private maintainer discussion first.
- **No credentials that aren't yours.** Vendor service passwords obtained informally, dealer tool licenses, "engineering mode" codes from unofficial sources - not usable as a basis for adapter work.
- **No contributions against NDAs you've signed.** If your knowledge of the protocol comes from working at or with the vendor under confidentiality, you are the wrong person to write this adapter, however clean your intentions. Hand your machine access (not your knowledge) to someone else.
- **The read-only constitution applies during research too.** Probing with read/poll commands is fine; discovering write commands means documenting their existence and never using them.

## 3. Clean Method, Step by Step

### 3.1 Establish your right to observe

Get the machine owner's permission in writing (an email or a signed line in the factory's cooperation note suffices) - naming the machine, the purpose (data interoperability), and the read-only commitment. For your own equipment, note the purchase basis. This one paragraph is disproportionately valuable later.

### 3.2 Capture

- `omp-sniff` in passive mode wherever possible - serial taps, mirrored switch ports, inline capture. Passive observation is the strongest position.
- Where the protocol requires solicitation (poll/response buses), send only request/read frames, ideally frames you first observed a vendor terminal send.
- **Annotate in real time.** `capture-2026-07-19.ndjson` plus a log: "14:02 machine idle · 14:05 operator started program 12 · 14:31 heat phase visibly began (panel showed 60C target)". Correlation between annotations and traffic is how decoding actually happens, and the annotations are themselves clean-room evidence.

### 3.3 Decode and document

- Work hypothesis-by-hypothesis in `PROTOCOL.md` - "bytes 4-5 LE u16 tracks panel cycle counter (confirmed across 3 sessions)" - keeping confirmed and suspected findings separated.
- Date your notes. Contemporaneous, dated, versioned (it's in git - good) documentation IS the clean-room record; no separate ceremony needed.
- Record provenance for every external input - "framing understood from vendor's public manual rev C, section 7" vs "checksum determined empirically from 200 frames".

### 3.4 The method statement

Every reverse-engineered adapter's PROTOCOL.md ends with a short, factual statement:

> Protocol knowledge in this document derives from (a) passive observation of serial traffic on a machine owned and operated by [factory], with written permission, using omp-sniff, during July 2026; (b) the vendor's publicly published operator manual [title, rev]. No vendor firmware or software was extracted, decompiled, or consulted. No confidential vendor documentation was used. All probing was read-only.

Maintainers check for this statement at review. It is two minutes of work that makes the contribution defensible for everyone downstream.

## 4. Trademark and Naming

- Adapter names may use vendor names **descriptively** - `sedo-treepoint` accurately describes compatibility. READMEs MUST carry the standard notice: *"[Vendor] and [product] are trademarks of their respective owners. This project is not affiliated with or endorsed by [vendor]."*
- Never imply endorsement, never use vendor logos, never name an adapter in a way that suggests it IS vendor software.

## 5. If a Vendor Objects

Refer any vendor contact - friendly or legal - to the core maintainers immediately rather than responding personally. The project's posture is cooperative: our preferred outcome with any vendor is the vendor-verified tier (GOVERNANCE.md 6.3), where objection turns into co-maintenance. Historically, in adjacent ecosystems, documented-clean interoperability work plus a cooperative posture resolves the overwhelming majority of vendor concerns without conflict, and the clean-room record you kept is exactly what makes that conversation short.

## 6. Jurisdiction Notes (non-exhaustive, verify locally)

- **EU** - Software Directive art. 6 protects decompilation for interoperability under conditions; passive protocol observation is generally on firmer ground still.
- **US** - interoperability reverse engineering has strong case-law support (Sega v. Accolade lineage); DMCA anti-circumvention is the live constraint - hence the bright line on protection measures.
- **Bangladesh, Vietnam, India, and similar** - copyright statutes generally track Berne/TRIPS and rarely address reverse engineering explicitly; the practical constraints are contract (NDAs, purchase terms) and imported vendor terms. The clean method above is protective everywhere precisely because it doesn't depend on any jurisdiction's most permissive reading.
- Machines under lease or service contracts may carry terms restricting "modification or analysis" - observation of data output is usually distinguishable from modification, but check the contract, and get the owner's written permission regardless (3.1 covers this).

## 7. Summary Card

Print this, tape it to the bench:

- ✅ Own/permitted machine, written note
- ✅ Passive capture first, read-only probes only
- ✅ Annotate captures in real time
- ✅ Dated notes in git, provenance for every fact
- ✅ Method statement in PROTOCOL.md
- ❌ No firmware, no decompiling vendor code
- ❌ No NDA'd or leaked docs, no borrowed credentials
- ❌ No defeating encryption/auth - escalate instead
- ❌ Never send state-changing commands
