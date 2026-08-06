# generic-modbus

The highest-leverage adapter: Modbus RTU/TCP devices join OMP with a YAML
register map, no code. Mapping format and a worked example live in
[First Real Machine section 4](../../docs/docs/getting-started/first-real-machine.md).

- **Maintainer**: core maintainers (seeking a hardware-owning co-maintainer)
- **Modes**: `on_increment` (counters → events), `on_change` (state registers →
  `state_change` with enum labels), `stats` (analog registers → telemetry
  stats blocks)
- **Register types**: `u16`, `s16`, `u32`, `u32_swapped`, with `scale`
- **Addressing**: conventional numbers (`40021` holding, `30007` input) or
  plain offsets
- **Read-only by construction**: the protocol layer implements only read
  function codes (0x03/0x04); there is no code path that can write to a
  device. This is the constitutional line, enforced structurally.
- **PROTOCOL.md exemption**: Modbus is a published open protocol
  (modbus.org); no reverse-engineering method statement applies.
- **Soak declaration**: framing verified against protocol test vectors and
  injected-transport replay; no continuous run against real hardware yet -
  contribute one.

Dev/CI: config accepts an injectable `transport` callable and `max_polls`,
so the full poll-decode-emit path runs against fixtures without a PLC.
