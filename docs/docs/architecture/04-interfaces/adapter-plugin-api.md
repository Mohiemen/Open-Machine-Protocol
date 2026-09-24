# Adapter Plugin API v0.1

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/architecture/04-interfaces/adapter-plugin-api.md |
| **Audience** | Adapter authors, gateway core developers |
| **Companion** | Core Schema Specification, Writing an Adapter guide |
| **Last updated** | July 2026 |

RFC 2119 keywords apply.

---

## 1. Contract Overview

An adapter is a Python package that translates one machine family's native signals into OMP message bodies. The gateway owns everything else - envelope construction, seq assignment, validation, checksumming, signing, buffering, export.

The division of responsibility is strict:

| Adapter does | Adapter MUST NOT |
|---|---|
| Speak the machine's protocol (serial, TCP, GPIO, vendor API) | Open network connections beyond its configured machine link |
| Translate signals to profile vocabulary | Assign `seq`, compute checksums, or sign anything |
| Emit bodies with `schema`, `profile`, and event time | Buffer to disk or export data |
| Report its own health honestly | Write to, command, or actuate the machine (constitutional) |
| Reconnect and recover from machine-side failures | Crash the gateway process (isolation, section 6) |

## 2. The Interface

```python
from omp.adapter import AdapterBase, Emit, MachineInfo, AdapterHealth

class Adapter(AdapterBase):

    #: Adapter identity, semver'd independently
    name: str = "generic-modbus"
    version: str = "0.1.0"

    #: Profiles this adapter can emit, most specific first
    supported_profiles: list[str] = ["textile-dyeing/0.1", "generic/0.1"]

    def probe(self, config: dict) -> MachineInfo:
        """Connect once, identify the machine, return identity and
        capabilities for machine.json. MUST complete or raise within
        the configured probe timeout (default 30 s). MUST be free of
        side effects on the machine."""

    def start(self, emit: Emit) -> None:
        """Begin continuous operation. Called in the adapter's own
        thread. MUST block until stop() is called, calling emit()
        for each observation. MUST handle machine-side disconnects
        internally with backoff, reporting them via health(), and
        keep trying until stopped."""

    def stop(self) -> None:
        """Signal start() to return. MUST cause start() to return
        within 10 s. Called from a different thread."""

    def health(self) -> AdapterHealth:
        """Cheap, thread-safe snapshot. Called at any time."""
```

### 2.1 Emit

```python
Emit = Callable[[Body], None]

@dataclass
class Body:
    schema: str            # machine | event | process_run | energy | telemetry
    profile: str           # e.g. "textile-dyeing/0.1"
    body: dict             # conforms to schema + profile
    event_ts: str | None   # machine-reported time if known, else None
                           # (gateway stamps receipt time when None)
```

`emit` is thread-safe and non-blocking up to the gateway's inbound queue limit; beyond it, `emit` blocks (backpressure). Adapters MUST tolerate emit blocking without losing machine-side data where the protocol allows (buffer small, poll less, or drop with a `maintenance_flag` event noting loss - never silently).

### 2.2 MachineInfo and AdapterHealth

```python
@dataclass
class MachineInfo:
    machine_class: str          # from a supported profile's taxonomy
    make: str | None
    model: str | None
    serial: str | None
    capabilities: list[str]     # schemas this source will emit
    data_source: str            # native | retrofit | hybrid

@dataclass
class AdapterHealth:
    state: str                  # ok | degraded | disconnected | failed
    connected_since: str | None
    last_data_ts: str | None
    reconnect_count: int
    error_count: int
    detail: str | None          # human-readable, one line
```

Health rules - `ok` means data flowed within the expected cadence; `degraded` means connected but abnormal (checksum errors on the wire, partial reads); `disconnected` means actively retrying; `failed` means the adapter has concluded it cannot recover without operator action (bad config, unsupported firmware) and retrying has stopped.

## 3. Configuration

Each machine's registry entry passes an adapter-defined `config` dict. Adapters MUST ship a JSON Schema for their config (`config.schema.json` in the adapter package) - the gateway validates registry entries against it at startup, turning YAML typos into startup errors instead of 3 a.m. mysteries.

Convention for common fields (use these names when applicable): `port`, `baud`, `host`, `tcp_port`, `unit_id`, `poll_interval_ms`, `timeout_ms`, `profile_hint`, `mapping_file`.

Secrets (device passwords) are referenced as `env:VAR_NAME` strings, resolved by the gateway; adapters never see registry files, only resolved dicts.

## 4. Lifecycle and Threading

```
gateway start
  └─ for each machine: load adapter package
       └─ validate config against config.schema.json
       └─ probe()  ──fail──▶ machine marked failed, others continue
       └─ spawn thread ──▶ start(emit)
                              │ (runs until...)
gateway stop / registry reload
  └─ stop()  ──▶ start() returns ──▶ thread joined (10 s deadline)
```

- One adapter instance per machine, even for multi-drop buses - shared transports are managed via the gateway's transport pool (`self.transport(...)` helper on AdapterBase) so two instances can share one RS485 line safely:

```python
link = self.transport(                     # key by the PHYSICAL link,
    f"modbus-rtu://{cfg['port']}",         # never by machine
    lambda: serial.Serial(cfg["port"], cfg.get("baud", 9600), timeout=2),
)

def poll(request: bytes) -> bytes:
    def txn(port):                         # write AND read inside one
        port.reset_input_buffer()          # exchange - this is the contract
        port.write(request)
        return port.read(256)
    try:
        return link.exchange(txn)
    except OSError:
        link.reset()                       # neighbours reopen on demand
        raise
```

  The atomic unit on a multi-drop bus is the whole **transaction**, not the individual read and write. Splitting them lets another machine's request land between yours and its reply, and both adapters then parse the wrong response - a failure that looks like random CRC errors on real hardware. `exchange()` holds the bus for the entire round trip; `reset()` drops a failed link so the next exchange reopens it without wedging the other machines on the bus. The gateway calls `release_transports()` after `stop()`, and the link closes when its last user lets go.
- Adapters MUST be import-safe - no I/O at import time.
- Restart policy on crash - exponential backoff (1 s to 5 min), crash count in health, machine marked `failed` after the configured limit.

## 5. Time and Ordering Duties

- Set `event_ts` only when the machine itself reports a timestamp or the adapter observed the instant directly. When reconstructing history after a reconnect (e.g. reading a controller's internal log), set `event_ts` from the log and emit in log order - the gateway assigns `seq` in emit order, so adapter emit order defines the canonical machine order.
- Adapters MUST NOT reorder observations across a reconnect boundary in ways that interleave old and new; drain recovered history first, then resume live.

## 6. Isolation and Safety

- Adapter exceptions escaping `start()` are caught by the gateway, logged, and trigger restart policy - but adapters SHOULD catch their own expected failure modes and count them in health rather than crash-looping.
- The gateway runs adapters with no filesystem access expectations beyond a per-adapter scratch dir (`self.scratch_dir`) and, obviously, their device nodes. Future hardening (subprocess isolation, seccomp) is roadmap; adapters that follow this contract today will not notice the change.
- Reminder of the constitutional line - if a protocol requires sending commands merely to elicit data (a poll request, a read register command), that is permitted; anything that changes machine state or behavior is not. Where a vendor protocol ambiguously mixes reads with state effects, document the analysis in the adapter README and choose the conservative path.

## 7. Testing and Conformance

An adapter PR MUST include:

1. **Unit tests** with the machine side mocked (fixtures of real captured traffic strongly preferred - omp-sniff captures drop in directly).
2. **Conformance run** - CI pipes the adapter's emitted bodies (driven by fixtures) through `omp-validate` against every profile in `supported_profiles`.
3. **A soak declaration** - the author states the longest continuous run achieved against real hardware or a hardware-faithful simulator, and known failure modes. Honesty here is a review criterion; "8 hours, loses connection on power dip, recovers in under 60 s" is a perfectly acceptable declaration.

## 8. Minimal Complete Example

```python
"""Adapter for a hypothetical cycle-counting controller that prints
'CYCLE <n>\\r\\n' on RS232 after each sewing cycle."""

import serial, threading, time
from omp.adapter import AdapterBase, Emit, MachineInfo, AdapterHealth, now_iso

class Adapter(AdapterBase):
    name = "example-cyclecounter"
    version = "0.1.0"
    supported_profiles = ["textile-sewing/0.1", "generic/0.1"]

    def probe(self, config):
        with serial.Serial(config["port"], config.get("baud", 9600), timeout=5) as s:
            s.readline()  # confirm the device talks
        return MachineInfo(
            machine_class="lockstitch", make=None, model=None, serial=None,
            capabilities=["event"], data_source="native",
        )

    def start(self, emit: Emit):
        self._stop = threading.Event()
        cycles = 0
        while not self._stop.is_set():
            try:
                with serial.Serial(self.config["port"],
                                   self.config.get("baud", 9600), timeout=1) as s:
                    self._mark_connected()
                    while not self._stop.is_set():
                        line = s.readline().decode(errors="replace").strip()
                        if line.startswith("CYCLE"):
                            cycles += 1
                            emit(self.body(
                                schema="event",
                                profile="textile-sewing/0.1",
                                body={"event_type": "cycle_complete",
                                      "payload": {"cycle_count": cycles}},
                            ))
            except serial.SerialException as e:
                self._mark_disconnected(str(e))
                self._stop.wait(self.backoff())

    def stop(self):
        self._stop.set()

    # health() provided by AdapterBase from _mark_* calls
```

Roughly 40 lines for a working adapter. That is the intended experience.
