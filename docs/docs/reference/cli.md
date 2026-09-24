# CLI reference

| | |
|---|---|
| **Status** | Available - v0.1.0 |
| **Location** | docs/reference/cli.md |
| **Scope** | `omp-validate`, `omp-simulate`, `omp-sniff`, `omp-gateway` |

This page documents the four shipped binaries from their `--help` output.
Installation and adapter-specific setup live in the [tools
README](../../../tools/README.md) and [gateway README](../../../gateway/README.md).
All version output in this page is `0.1.0`.

## Common behavior

- Every binary supports `--version`, which prints the program name and version
  and exits with status 0.
- Every binary uses Python `argparse`; unknown flags and invalid required
  arguments exit with status 2.
- Help output is available with `-h` or `--help`.

## `omp-validate`

Validate an NDJSON stream of OMP envelopes. Validation order per message is:
envelope schema, body schema, checksum, then the declared profile's
constraints. First failure wins for reporting; the message counts as invalid
either way.

```text
usage: omp-validate [-h] [--spec-dir SPEC_DIR] [--quiet] [--pubkey BASE64]
                    [--audit] [--run-id RUN_ID] [--version]
                    [files ...]
```

`files` are NDJSON files. When omitted, `omp-validate` reads stdin.

| Option | Description |
|---|---|
| `--spec-dir SPEC_DIR` | Path to the spec directory. |
| `--quiet` | Print only the summary line. |
| `--pubkey BASE64` | Verify Ed25519 signatures against this gateway public key. Envelopes without a signature fail. |
| `--audit` | Audit an evidence bundle: run the five DPP checks over the envelopes of one process run and print the citation block. |
| `--run-id RUN_ID` | Which run to audit when the bundle covers several. |
| `--version` | Print `omp-validate 0.1.0` and exit. |

Exit status:

- `0` - every envelope was valid.
- `1` - at least one envelope was invalid.
- `2` - usage error.

Example:

```sh
$ omp-simulate --profile generic --machines 1 --duration 10s --seed 2 | omp-validate --quiet
✔ 4 messages valid (schema: event x2, machine x1, process_run x1)
```

Invalid input:

```sh
$ printf '{}\n' | omp-validate --quiet
0 valid, 1 invalid (details above)
```

## `omp-simulate`

Generate realistic OMP envelope streams without hardware. Output is NDJSON on
stdout, or MQTT with `--export`. Simulated time emits immediately, so a
`--duration` of `8h` does not wait eight hours.

```text
usage: omp-simulate [-h] [--profile {generic,textile-sewing,textile-dyeing}]
                    [--machines MACHINES] [--duration DURATION] [--seed SEED]
                    [--chaos {corrupt-fields}] [--chaos-rate CHAOS_RATE]
                    [--export mqtt://HOST[:PORT]] [--site SITE] [--line LINE]
                    [--version]
```

| Option | Default | Description |
|---|---|---|
| `--profile` | `generic` | `generic`, `textile-sewing`, or `textile-dyeing`. |
| `--machines` | `1` | Number of simulated machines. |
| `--duration` | `10m` | Simulated wall time, e.g. `10s`, `5m`, `8h`. |
| `--seed` | none | Random seed for reproducible streams. |
| `--chaos` | none | `corrupt-fields` to emit invalid envelopes for validation demos. |
| `--chaos-rate` | `0.05` | Probability that chaos corrupts a field. |
| `--export` | none | `mqtt://HOST[:PORT]` export destination. |
| `--site` | `demo` | Site identifier. |
| `--line` | `line1` | Line identifier. |
| `--version` | - | Print `omp-simulate 0.1.0` and exit. |

The identity caveat is important for fixtures: `gateway_id` is always
`gw-sim-01`, and machine ids derive from `--line` and the machine index. Two
invocations therefore produce envelopes sharing `(gateway_id, machine_id,
seq)` with different content. Feed one simulator run per consumer or rewrite
the ids.

Example:

```sh
$ omp-simulate --profile generic --machines 1 --duration 10s --seed 1 | head -n 1
{"omp_version": "0.1.0", "profile": "generic/0.1", "gateway_id": "gw-sim-01", "machine_id": "sim-line1-m01", "seq": 1, ...}
```

## `omp-sniff`

Passively capture raw traffic into annotated NDJSON records that can become
adapter replay fixtures. This tool never transmits.

```text
usage: omp-sniff [-h] (--serial PORT | --stdin | --decode FILE) [--baud BAUD]
                 [--out FILE] [--version]
```

Exactly one mode is required:

| Option | Description |
|---|---|
| `--serial PORT` | Capture from a serial port. Requires `pyserial`. |
| `--stdin` | Capture lines from stdin, e.g. pipes, `socat`, or replays. |
| `--decode FILE` | Pretty-print a capture for protocol study. |

Additional options:

| Option | Default | Description |
|---|---|---|
| `--baud` | `9600` | Serial baud rate. |
| `--out FILE` | stdout | Write capture to a file instead of stdout. |
| `--version` | - | Print `omp-sniff 0.1.0` and exit. |

Record format is one JSON object per line:

```text
{"t": "<iso8601>", "src": "<source>", "hex": "41 42 ...", "text": "<text>"}
```

Annotations typed on a TTY prompt, or lines starting with `#` in stdin mode,
become records with `"note"`.

Example:

```sh
$ printf '# annotation\nABCD\n' | omp-sniff --stdin
{"t": "2026-08-06T18:55:00.584Z", "note": "annotation"}
{"t": "2026-08-06T18:55:00.584Z", "src": "stdin", "hex": "41 42 43 44", "text": "ABCD"}
```

## `omp-gateway`

Edge gateway for adapters, validation, buffering, signing, and export.

```text
usage: omp-gateway [-h] [--version]
                   {run-once,install-service,show-identity,run,reload,tail,
                    status,audit-host,verify-release,dead-letters}
                   ...
```

| Subcommand | Purpose |
|---|---|
| `run-once` | Drive one adapter and print validated envelopes. |
| `install-service` | Create state dirs, keypair, and registry template; print the systemd unit. |
| `show-identity` | Print `gateway_id` and public key. |
| `run` | Run the gateway from a registry. |
| `reload` | Tell a running gateway to re-read its registry. |
| `tail` | Stream the buffer as NDJSON without acking anything. |
| `status` | Report machines, buffer, and dead letters. |
| `audit-host` | Check the host against Hardening Guide s3 and report drift. |
| `verify-release` | Verify a downloaded release artifact's minisign signature. |
| `dead-letters` | Print recent dead letters. |

### `run-once`

```text
usage: omp-gateway run-once [-h] --adapter ADAPTER --config CONFIG
                            [--duration DURATION] [--gateway-id GATEWAY_ID]
                            [--state-dir STATE_DIR] [--spec-dir SPEC_DIR]
```

| Option | Default | Description |
|---|---|---|
| `--adapter` | required | Path to the adapter directory. |
| `--config` | required | Dev config YAML. |
| `--duration` | `10` | Seconds to run. |
| `--gateway-id` | `gw-dev-01` | Gateway identifier for emitted envelopes. |
| `--state-dir` | temp dir | Persist sequence and buffer here instead of a temp dir. |
| `--spec-dir` | auto | Path to the spec directory. |

### `install-service`

```text
usage: omp-gateway install-service [-h] [--prefix PREFIX]
                                   [--state-dir STATE_DIR]
                                   [--gateway-id GATEWAY_ID]
```

| Option | Default | Description |
|---|---|---|
| `--prefix` | `/etc/omp` | Config directory. |
| `--state-dir` | `/var/lib/omp` | State directory. |
| `--gateway-id` | `gw-<hostname>` | Gateway identifier. |

Example with non-system paths:

```sh
$ omp-gateway install-service --prefix /tmp/omp/etc --state-dir /tmp/omp/state --gateway-id gw-doc
gateway_id: gw-doc
pubkey: ed25519:<generated public key>
# record both in your key registry now (DPP Evidence Chain s6)
# systemd unit (write to /etc/systemd/system/omp-gateway.service):
[Unit]
...
```

### `show-identity`

```text
usage: omp-gateway show-identity [-h] [--prefix PREFIX]
                                 [--state-dir STATE_DIR]
```

`--prefix` defaults to `/etc/omp` and `--state-dir` defaults to
`/var/lib/omp`. It prints two lines:

```text
gateway_id: <id>
pubkey: ed25519:<public key>
```

### `run`

```text
usage: omp-gateway run [-h] --registry REGISTRY --state-dir STATE_DIR
                       [--adapters-dir ADAPTERS_DIR] [--gateway-id GATEWAY_ID]
                       [--sign] [--duration DURATION] [--spec-dir SPEC_DIR]
                       [--retention-days RETENTION_DAYS]
                       [--max-buffer-bytes MAX_BUFFER_BYTES]
                       [--prune-interval PRUNE_INTERVAL]
                       [--max-crashes MAX_CRASHES]
                       [--probe-timeout PROBE_TIMEOUT]
```

| Option | Default | Description |
|---|---|---|
| `--registry` | required | Registry YAML path. |
| `--state-dir` | required | State directory. |
| `--adapters-dir` | `adapters` | Directory containing adapter packages by name. |
| `--gateway-id` | from state dir | Gateway identifier. |
| `--sign` | off | Sign envelopes with `<state-dir>/keys/gateway.pem`; created if absent. |
| `--duration` | forever | Run for N seconds then exit. |
| `--spec-dir` | auto | Path to the spec directory. |
| `--retention-days` | `30` | Prune delivered envelopes older than this. |
| `--max-buffer-bytes` | none | Also prune when the buffer database exceeds this size. |
| `--prune-interval` | `3600` | Seconds between retention passes. |
| `--max-crashes` | `5` | Mark a machine failed after this many adapter crashes. |
| `--probe-timeout` | `30` | Seconds a `probe()` may take before the machine is marked failed. |

### `reload`

```text
usage: omp-gateway reload [-h] --state-dir STATE_DIR
```

Tells a running gateway to re-read its registry.

### `tail`

```text
usage: omp-gateway tail [-h] --state-dir STATE_DIR [--follow] [--no-follow]
                        [--last N] [--machine MACHINE] [--poll POLL]
```

| Flag | Default | Meaning |
|---|---|---|
| `--follow`, `-f` | on | Keep streaming as new envelopes arrive. |
| `--no-follow` | - | Print what is buffered and exit. Starts from the beginning. |
| `--last N` | all | Start N envelopes back instead. |
| `--machine` | all | Only this `machine_id`. |
| `--poll` | `0.5` | Seconds between checks while following. |

`tail` is **read-only**: it never advances an exporter cursor, so watching a
stream cannot cause retention to prune data no exporter delivered.

```sh
$ omp-gateway tail --state-dir /var/lib/omp | omp-validate
```

Ctrl-C ends the pipeline with a validation summary rather than a traceback.

### `status`

```text
usage: omp-gateway status [-h] --state-dir STATE_DIR
```

Example after `install-service` with no machines:

```sh
$ omp-gateway status --state-dir /tmp/omp/state
machines: 0  buffered: 0  dead_letters: 0  buffer_db: 40 KiB
```

### `dead-letters`

```text
usage: omp-gateway dead-letters [-h] --state-dir STATE_DIR [--limit LIMIT]
```

`--limit` defaults to `20`. An empty dead-letter queue prints nothing.

Example:

```sh
$ omp-gateway dead-letters --state-dir /tmp/omp/state --limit 3
```

### `audit-host`

```text
usage: omp-gateway audit-host [-h] [--state-dir STATE_DIR] [--root ROOT]
                              [--service-user SERVICE_USER]
                              [--save-baseline] [--strict-unknown] [--json]
```

Checks the [Hardening Guide](../security/hardening-guide.md) s3 Required host
items - dedicated device, SSH policy, unattended-upgrades, the unprivileged
service user, serial device-group access - plus keypair permissions (s4) and
NTP sync. With `--state-dir` it stores a baseline and reports **drift** on
later runs, including changes in the evidence behind a check that still
passes.

| Flag | Default | Meaning |
|---|---|---|
| `--state-dir` | none | Inspect the keypair here, and store the drift baseline here. |
| `--root` | `/` | Audit a different filesystem tree (testing, or an image). |
| `--service-user` | `omp` | The user the gateway service runs as. |
| `--save-baseline` | - | Record this result as the baseline. Needs `--state-dir`. |
| `--strict-unknown` | - | Exit non-zero when a Required check cannot be evaluated. |
| `--json` | - | Machine-readable output for monitoring. |

| Exit | Meaning |
|---|---|
| `0` | No Required check failing, no drift. |
| `1` | Drift since the baseline, nothing Required failing. |
| `2` | A Required check is failing. |

A check that cannot be evaluated prints `?` and is counted separately - it is
**not** a pass. The report also names what it did not check (segmentation,
broker ACLs, release verification), so a clean run is not a clean deployment.

```sh
$ omp-gateway audit-host --state-dir /var/lib/omp --save-baseline
```

### `verify-release`

```text
usage: omp-gateway verify-release [-h] [--signature SIGNATURE]
                                  [--pubkey PUBKEY] [--checksums CHECKSUMS]
                                  artifact
```

Verifies a downloaded release against a minisign signature
([Hardening Guide](../security/hardening-guide.md) s6 **[Required]**). Both
the prehashed (`ED`) and legacy (`Ed`) formats, and the trusted comment's own
global signature - so a version string cannot be rewritten under a valid file
signature.

| Flag | Default | Meaning |
|---|---|---|
| `--signature` | `<artifact>.minisig` | The signature file. |
| `--pubkey` | none | The trusted public key. Required - no key ships yet. |
| `--checksums` | none | A `SHA256SUMS` file to cross-check. |

Obtain the public key through a channel **independent of the artifact**. A key
downloaded beside the file it signs proves only that one party controlled
both. This command never fetches a key for you.

Exit is `0` only when a signature was checked and passed. No key, no
signature file, or an unreadable one is exit `1` with the reason - "cannot
verify" never looks like "verified".

```sh
$ omp-gateway verify-release omp-gateway-0.1.0.tar.gz --pubkey omp-release.pub
✔ omp-gateway-0.1.0.tar.gz verified
  key      9C66E4CFE77177E2  (minisign public key 9C66E4CFE77177E2)
  comment  OMP 0.1.0 tag v0.1.0 built 2026-09-24
  sha256   22020adc360051cc624c3954c22d28e1f10519d7fefe35ea2f70ce0519bc8af9
```

An unsigned `SHA256SUMS` is reported as adding no provenance, not as a pass.

## See also

- [Quickstart](../getting-started/quickstart.md)
- [Writing an Adapter](../guides/writing-an-adapter.md)
- [Core spec](../../spec/omp-schema-v0.1.md)
