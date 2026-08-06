---
name: run-open-machine-protocol
description: Build, run, test, and drive the Open Machine Protocol (OMP) gateway, CLIs, and adapters. Use when asked to run OMP, start the gateway, simulate or validate machine data, drive or test an adapter without hardware, verify envelope signatures, or smoke-test the repo.
---

OMP is a Python monorepo: two installable packages (`gateway/`, `tools/`)
providing four CLIs, plus `adapters/`, `examples/`, and the normative spec
under `docs/spec/`. **There is no GUI and no long-lived server to babysit** —
everything is driven from the shell, and the agent path is
`.claude/skills/run-open-machine-protocol/driver.py`, which launches the real
gateway, drives real adapters, and asserts on the output.

All paths below are relative to the repo root.

## Prerequisites

Python 3.11+ only. No `apt-get` packages are needed — this container already
had everything. **Use a venv**; see Gotchas for why system Python bites.

```bash
python3 -m venv /tmp/ompclean
```

## Setup

Both packages, editable. `gateway` depends on `tools` at runtime, so install
them together:

```bash
/tmp/ompclean/bin/pip install -e ./gateway -e ./tools
```

Verify all four CLIs landed:

```bash
/tmp/ompclean/bin/omp-validate --version   # → omp-validate 0.1.0
/tmp/ompclean/bin/omp-simulate --version   # → omp-simulate 0.1.0
/tmp/ompclean/bin/omp-sniff --version      # → omp-sniff 0.1.0
/tmp/ompclean/bin/omp-gateway --version    # → omp-gateway 0.1.0
```

No build step — pure Python.

## Run (agent path)

One command drives everything: install check, the documented quickstart
pipeline for all three profiles, every conformance vector, a real adapter
through the real engine, a signed gateway daemon run with signature
verification, and the reference consumer.

```bash
/tmp/ompclean/bin/python .claude/skills/run-open-machine-protocol/driver.py all
# → ... all driver checks passed     (exit 0; exit 1 on any failure)
```

Run one stage at a time while iterating:

| subcommand | what it does |
|---|---|
| `doctor` | CLIs on PATH, packages importable, 6 schemas + 3 profiles load, signing available |
| `quickstart` | `omp-simulate \| omp-validate` for generic / textile-sewing / textile-dyeing, then asserts `--chaos corrupt-fields` **fails** with exit 1 |
| `conformance` | every vector in `docs/spec/conformance/` and `docs/spec/profiles/*/conformance/` through the validator (36 of them) |
| `adapter` | drives an adapter through the real gateway engine — **no hardware** |
| `gateway` | full `omp-gateway run --sign` daemon, then verifies every signature and rejects a tampered `seq` |
| `consumer` | reference platform consumer with the guide's edge cases (duplicate, integrity alarm, seq gap, malformed input) |
| `all` | all of the above |

### Driving an adapter you're working on

This is the path most adapter PRs need — it runs your adapter through the
real `Engine` (validation, seq assignment, checksums, dead letters) without a
PLC or serial port:

```bash
cat > /tmp/lines.yaml <<'YAML'
profile: textile-dyeing/0.1
machine_class: jigger
patterns:
  - match: '^TEMP=(?P<c>\d+)$'
    emit: { schema: telemetry, channel: bath_temp, unit: Cel, value: c, mode: stats }
  - match: '^PHASE (?P<name>\w+) START$'
    emit: { schema: event, event_type: phase_start, payload: { phase: name } }
YAML
printf 'TEMP=30\nPHASE heat START\nTEMP=60\nPHASE hold START\n' > /tmp/cap.txt
cat > /tmp/cfg.json <<'JSON'
{"line_profile": "/tmp/lines.yaml", "replay_file": "/tmp/cap.txt", "stats_window_s": 0.0}
JSON

/tmp/ompclean/bin/python .claude/skills/run-open-machine-protocol/driver.py \
  adapter adapters/generic-serial --config /tmp/cfg.json \
  --machine-id f1-dye-jig01 --expect 3 --print-envelopes
# → 3 envelope(s) emitted, each "seq N ... conformant", no dead letters
```

With no arguments it runs a built-in `generic-serial` replay demo that needs
no fixtures:

```bash
/tmp/ompclean/bin/python .claude/skills/run-open-machine-protocol/driver.py adapter
# → 4 envelopes from the replay capture, all conformant, no dead letters
```

Every adapter here supports a **hardware-free mode** — use it:

| adapter | hardware-free config key |
|---|---|
| `generic-serial` | `replay_file` (text file of controller lines) |
| `generic-modbus` | `transport` (callable) + `max_polls`, or `framing: tcp` |
| `retrofit-esp32` | `messages` (list of node dicts) or `replay_file` (NDJSON) |

### Individual CLIs

```bash
/tmp/ompclean/bin/omp-simulate --profile textile-dyeing --machines 2 --duration 4h --seed 5 \
  | /tmp/ompclean/bin/omp-validate
# → ✔ 53 messages valid (schema: energy x2, event x33, machine x2, process_run x2, telemetry x14)
```

```bash
printf 'CYCLE 1\n# operator pressed start\nCYCLE 2\n' | /tmp/ompclean/bin/omp-sniff --stdin > /tmp/cap.ndjson
/tmp/ompclean/bin/omp-sniff --decode /tmp/cap.ndjson
# → 2026-08-06T16:01:35.746Z  CYCLE 1
#   2026-08-06T16:01:35.746Z  ── operator pressed start ──
```

The gateway daemon exits on its own with `--duration`; without it, it runs
until Ctrl-C. It writes NDJSON to stdout when no exporter is configured:

```bash
# reuses /tmp/lines.yaml and /tmp/cap.txt from the adapter section above
cat > /tmp/registry.yaml <<'YAML'
machines:
  - machine_id: f1-dye-jig01
    adapter: generic-serial
    profile: textile-dyeing/0.1
    config:
      line_profile: /tmp/lines.yaml
      replay_file: /tmp/cap.txt
      stats_window_s: 0.0
    location: { site: f1, area: dyeing, line: jigs, station: jig01 }
YAML

/tmp/ompclean/bin/omp-gateway run --registry /tmp/registry.yaml --state-dir /tmp/gwstate \
  --adapters-dir adapters --gateway-id gw-driver-01 --sign --duration 3
# → NDJSON envelopes on stdout, machine announcement first
/tmp/ompclean/bin/omp-gateway status --state-dir /tmp/gwstate
# → machines: 1  buffered: 5  dead_letters: 0
/tmp/ompclean/bin/omp-gateway show-identity --state-dir /tmp/gwstate
# → gateway_id: gw-driver-01 / pubkey: ed25519:...
```

## Test

```bash
/tmp/ompclean/bin/pip install pytest
/tmp/ompclean/bin/python -m pytest tools/tests gateway/tests -q
# → 81 passed in ~8s
```

Lint matches CI:

```bash
ruff check gateway/ tools/ adapters/ examples/
```

## Gotchas

- **`pip install -e ./tools` alone is not enough.** `omp-gateway` imports
  `omp_tools` for spec loading and validation at runtime and raises a
  pointed ImportError without it. Always install both packages.
- **The spec is data, loaded at runtime — not packaged.** `omp-validate`
  finds `docs/spec/` by walking up from the installed package's `__file__`,
  so an **editable** install works from any cwd (verified from `/tmp`), but a
  non-editable/wheel install would not. Override with `--spec-dir` or
  `OMP_SPEC_DIR`.
- **Adapters are loaded by path, not imported as packages.** They live in
  `adapters/<name>/adapter.py` with a sibling `protocol.py`; the loader
  injects the directory into `sys.path` and evicts it afterwards, because
  every adapter names that module `protocol` and two would otherwise collide
  in `sys.modules`. Don't `import protocol` from test code — use
  `omp.cli.load_adapter_class` or `importlib.spec_from_file_location`.
- **Checksums reject non-integral floats.** `omp_tools.envelope.canonicalize`
  raises rather than emit a checksum it can't guarantee is RFC 8785-correct,
  so producers must keep body numbers integral (this is why the simulator and
  the retrofit adapter emit whole units). A body with `1.5` in it dead-letters
  with "non-integral float".
- **Chaos mode is supposed to fail.** `omp-simulate --chaos corrupt-fields |
  omp-validate` exits 1 by design. CI asserts the failure; don't "fix" it.
- **`omp-gateway run | head` stops the gateway** — by design. A closed stdout
  raises `ExporterClosed`, which winds the daemon down cleanly instead of
  tracebacking, and the undelivered envelope stays **unacked in the buffer**
  (`status` will show `buffered: 3` with the cursor at row 2). That is
  at-least-once working correctly, not a leak.
- **MQTT is unverified in this container.** `--export mqtt://…` and the
  gateway's mqtt exporter need `pip install 'omp-tools[mqtt]'` plus a broker;
  neither `mosquitto` nor `paho` is present here, so the stdout/NDJSON path is
  the one to use. Same for `examples/grafana-dashboards/` — no Docker daemon.
- **The ESP32 firmware cannot be built here.** `pio run` fails at
  `Platform Manager: Installing espressif32 → HTTPClientError` (toolchain
  fetch blocked). The firmware is an uncompiled draft; see
  `retrofit/esp32-ct-clamp/README.md`.
- **Don't hand-edit conformance vectors.** Their checksums are real. Edit
  `docs/spec/conformance/tools/gen_vectors.py` and re-run it.

## Troubleshooting

- **`pyo3_runtime.PanicException: Python API call failed` with
  `ModuleNotFoundError: No module named '_cffi_backend'`** when importing
  `cryptography` (i.e. anything touching signing): you're on Debian's *system*
  Python, whose `cryptography` 41.0.7 ships without its cffi backend. Fix with
  `pip install cffi`, or avoid it entirely by using a venv as above.
- **`FileNotFoundError: .../state/gateway_id` from `show-identity`**: fixed —
  `run` now persists the id. If you see it on an older checkout, run
  `omp-gateway install-service --state-dir <dir>` first.
- **`omp-validate` says `spec directory not found`**: you have a
  non-editable install or moved `docs/`. Pass `--spec-dir docs/spec` or set
  `OMP_SPEC_DIR`.
- **Adapter emits nothing and health stays `disconnected`**: the replay file
  path is wrong or empty — the adapter reports it via `health().detail` rather
  than crashing. `driver.py adapter --print-envelopes` shows what came out.
