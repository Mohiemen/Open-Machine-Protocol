# Writing an Adapter

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/guides/writing-an-adapter.md |
| **You need** | Access to a machine (or good captures of one), working Python, the [Adapter Plugin API](../architecture/04-interfaces/adapter-plugin-api.md) open in another tab |
| **Target** | From "I have this machine" to merged PR in four weekends. This guide is structured as those four weekends. |

---

## Before You Start - Does This Need an Adapter at All?

- Machine speaks **Modbus**? Use `generic-modbus` with a mapping file - no code, see [First Real Machine](../getting-started/first-real-machine.md). Consider contributing your mapping file to `adapters/generic-modbus/maps/` instead; that helps everyone with your machine and takes an hour.
- Machine prints **parseable serial lines**? `generic-serial` with a line profile, same story.
- Machine has an **OPC UA server**? Wait for or help with `opcua-client`.

Write a dedicated adapter when the protocol is stateful, binary, session-based, or otherwise beyond declarative mapping - vendor network protocols, controller APIs, complex framing.

## Weekend 1 - Understand the Protocol

**Goal - a documented understanding, zero code.**

1. **Gather documentation.** Vendor comms manuals, integrator notes, existing open-source implementations in any language (check licenses before reading code closely - see the [reverse-engineering guide](reverse-engineering-protocols.md) for when NOT to look).
2. **Capture real traffic.** Run `omp-sniff` (serial or pcap mode) while operating the machine through its states - idle, running, faults if safely inducible, power-on sequence. **Annotate as you go** - a capture where you noted "10:41 operator pressed start" is worth ten clean ones.
3. **Write `PROTOCOL.md`** in your adapter directory as you decode - framing, checksums, message types, the meaning of each field you've confirmed, and a "suspected but unconfirmed" section. This file is a merge requirement and, for reverse-engineered protocols, your clean-room record.
4. **Decide your profile mapping.** Which profile events does each protocol message become? Where the machine reports something with no profile equivalent, note it - it either maps to a core event, waits, or becomes a profile RFC. Do not invent ad-hoc event types.

Checkpoint - a colleague could implement the adapter from your PROTOCOL.md without the machine. If not, keep capturing.

## Weekend 2 - Make It Work

**Goal - data flowing end to end against the real machine or replayed captures.**

```bash
cp -r adapters/_template adapters/myvendor-mymachine
cd adapters/myvendor-mymachine
```

The template gives you the package layout, `AdapterBase` subclass stubs, `config.schema.json`, a fixtures directory, and CI wiring.

Implementation order that works:

1. **`probe()`** - connect, identify, return `MachineInfo`. Get this solid; it's your connection code in miniature.
2. **A protocol layer module** (`protocol.py`) separate from the adapter class - pure functions from bytes to parsed messages. This is what your unit tests hit, and what makes review fast.
3. **`start()`** - the read loop calling `emit()`. Steal the reconnect/backoff skeleton from the API doc's example verbatim; it is correct and reviewers know it on sight.
4. **Replay mode from day one** - the template's `fixtures/replay.py` feeds captured traffic through your protocol layer. You will iterate 10x faster against replay than against a machine you have to walk over to.

Run it for real:

```bash
omp-gateway run-once --adapter ./adapters/myvendor-mymachine --config dev-config.yaml | omp-validate
```

Checkpoint - a full machine cycle produces valid, profile-conformant messages that tell the true story of what the machine did.

## Weekend 3 - Make It Honest and Robust

**Goal - the adapter survives reality and reports it truthfully.**

Work through this list against the real machine:

- **Pull the cable mid-run.** Health goes `disconnected`, reconnect with backoff, recovery without duplicate or interleaved history (API doc section 5).
- **Power-cycle the machine.** Does its controller replay old state on boot? Don't re-emit stale cycles as new.
- **Induce noise** (if serial) - health `degraded` with counted errors, not a crash, not silent garbage.
- **Let it soak.** Overnight minimum, a working day better. Memory flat? File handles stable? Note the result - your soak declaration (API doc section 7) goes in the PR honestly, including what still breaks.
- **Fill in `health()` details** a stranger at 3 a.m. would thank you for - "no response to poll on /dev/ttyUSB0 for 45 s" beats "error".
- **Config validation** - every config mistake you made yourself this weekend should now be a clear startup error via `config.schema.json`.

## Weekend 4 - Make It Mergeable

**Goal - a PR a maintainer can approve without owning your machine.**

1. **Unit tests** on `protocol.py` using your fixtures - happy paths, every fault mode you observed, truncated/corrupt frames.
2. **Conformance in CI** - the template's workflow pipes replayed fixtures through `omp-validate` for every profile in `supported_profiles`. Green locally first.
3. **README.md** - supported machines/firmware versions (tested vs expected), config reference generated from your schema, wiring notes with a photo if physical connection is non-obvious, known limitations.
4. **PROTOCOL.md** finalized, including the reverse-engineering method statement where applicable.
5. **Trim fixtures** - captures can contain serial numbers or production data; scrub or synthesize what you publish.
6. Open the PR, name yourself maintainer, fill the template. Review will focus on the emitted vocabulary and the reconnect behavior - the two things that outlive your code.

## Quality Bar, Summarized

An adapter is merged when a maintainer can believe three sentences:

1. *The emitted messages truthfully describe what the machine did* (fixtures + conformance prove it).
2. *It fails loudly and recovers automatically* (weekend 3's list proves it).
3. *Someone other than the author can deploy and debug it* (README + health details + config schema prove it).

## If You Get Stuck

- Protocol won't yield? Post annotated captures in an issue - collective decoding is a spectator sport here and people genuinely enjoy it.
- Profile has no vocabulary for something important? Discussion first, RFC if confirmed - you may have found a real profile gap, which is a contribution in itself.
- Ran out of weekends? Push the branch, mark it draft, state what's left. Half an adapter with good PROTOCOL.md and fixtures is a huge head start for the next person, and plenty of merged adapters finished as relay races.
