# esp32-ct-clamp - Bill of Materials

**Safety first**: CT clamp installation opens electrical panels. In most
facilities this legally and practically requires a qualified electrician;
nothing here overrides your lockout/tagout procedures. The electrician does
the panel work, you do the configuration
([retrofit guide](../../../docs/docs/guides/retrofit-installation.md)).

Total parts cost per node: roughly $12-20 depending on sourcing.

| Part | Spec | Notes |
|---|---|---|
| ESP32 dev board | ESP32-WROOM-32 (e.g. "ESP32 DevKitC") | NOT the -C3 minimal boards - different ADC |
| CT clamp | SCT-013 series split-core, **voltage output (1V)** variant | Size to the machine's breaker: 30 A single sewing machines, 100 A dye machine mains |
| Burden/bias circuit | 2x 10 kΩ (Vcc/2 divider), 1x 10 µF electrolytic, plus 33 Ω burden ONLY for current-output CT variants | Or the ready-made "CT sensor module" boards that integrate this |
| Power supply | 5 V / 1 A+, quality brand | The no-name chargers are the top field failure - keep spares |
| Enclosure | Any IP54 junction box | Printable STL: contribution-wanted; conformal-coat boards for dye houses |
| Wiring | Screw-terminal breakout for the ESP32 | Solder-free assembly fully supported and recommended for first builds |

## Wiring (voltage-output SCT-013, e.g. 30A/1V)

```
3V3 ──┬── 10kΩ ──┬── 10kΩ ── GND      (bias divider -> Vcc/2)
      │          │
      │         ─┴─ 10µF ── GND
      │          │
CT tip ──────────┤
CT sleeve ───────┴───────── GPIO34 (ADC1_CH6)
```

- One phase conductor only through the clamp - line+neutral together cancels
  to zero.
- Current-output CT variants (e.g. 100A/50mA) additionally need the 33 Ω
  burden resistor across the CT before the bias point.

**Status**: circuit is the standard OpenEnergyMonitor-style arrangement but
this specific BOM has not been bench-validated with this firmware - the
firmware's calibration constants need verification against a reference
meter. KiCad schematic/PCB and enclosure STLs are contribution-wanted.
Local sourcing notes (AliExpress part numbers, Dhaka suppliers) welcome via
PR to this file.
