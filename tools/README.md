# omp-tools

`omp-validate` and `omp-simulate` - the no-hardware entry point to OMP.

```bash
pip install -e ./tools            # from the repo root; add [mqtt] for --export
omp-simulate --profile textile-sewing --machines 10 --duration 10m | omp-validate
```

- **omp-validate** checks NDJSON envelopes against the normative artifacts in
  `docs/spec/` - envelope schema, body schema, RFC 8785 checksum, and the
  declared profile's event/phase constraints. Exit 1 if anything is invalid.
  Passing all of `docs/spec/conformance/` is enforced in this package's tests.
- **omp-simulate** generates conformant streams for `generic`,
  `textile-sewing` (cycle-based line), and `textile-dyeing` (batch with the
  full phase skeleton). `--chaos corrupt-fields` demonstrates validation
  biting; `--export mqtt://host:1883` publishes on the
  `omp/{site}/{area}/{line}/{machine}/{schema}` topic convention.

Spec discovery: `--spec-dir`, `OMP_SPEC_DIR`, or automatic when running from
a repo checkout. See [the quickstart](../docs/docs/getting-started/quickstart.md).

- **omp-sniff** captures protocol traffic to annotated NDJSON that drops
  straight into adapter replay fixtures - `--serial PORT` (needs pyserial),
  `--stdin` for pipes/socat, `--decode FILE` for protocol study, `#`-prefixed
  lines and TTY input become timestamped annotations. Passive only; it never
  transmits. pcap mode is roadmap - use tcpdump and contribute the capture.

See the [milestone plan](../docs/docs/architecture/10-roadmap/milestone-plan.md)
for what's still open.
