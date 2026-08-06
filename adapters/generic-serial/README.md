# generic-serial

Profile-driven adapter for legacy controllers that print parseable lines over
RS232/RS485 (`TEMP=060.5`, `PHASE HEAT START`, `CYCLE 1042`).

- **Maintainer**: core maintainers (seeking a hardware-owning co-maintainer)
- **Machines**: any controller with documented (or sniffed) line output
- **Config**: see `config.schema.json`; line profile format in
  [First Real Machine section 5](../../docs/docs/getting-started/first-real-machine.md)
- **No hardware?** `replay_file` drives the adapter from an `omp-sniff`
  capture or any text file of lines - this is how CI runs it.
- **Soak declaration**: replay-tested only so far; no continuous run against
  real hardware yet. If you run one, report it - honesty here is the review
  criterion.

Telemetry patterns aggregate to `stats` blocks per the spec's guidance
(window `stats_window_s`, default 60 s); events emit immediately.
