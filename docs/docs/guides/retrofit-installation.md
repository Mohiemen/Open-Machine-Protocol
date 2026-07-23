# Retrofit Installation - ESP32 Kits for Machines With No Digital Output

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/guides/retrofit-installation.md |
| **You need** | The kit for your sensor type (BOM below), a 2.4 GHz WiFi SSID reachable from the machine, basic electrical competence, a running gateway ([First Real Machine](../getting-started/first-real-machine.md) section 2) |
| **Time** | One afternoon for the first node, under an hour per node after that |

**Safety first.** CT clamp installation involves opening electrical panels. In most facilities this legally and practically requires a qualified electrician. Nothing in this guide overrides your factory's electrical safety procedures, lockout/tagout rules, or local regulations. When in doubt, the electrician does the panel work and you do the configuration.

---

## 1. Choose Your Kit

| Kit | Measures | Emits | Best for |
|---|---|---|---|
| `esp32-ct-clamp` | Current draw via non-invasive clamp | `energy` (kWh intervals), `event` start/stop inferred from load | Any machine, the universal starting point |
| `esp32-vibration` | Vibration RMS via accelerometer | `telemetry` (vibration channels), `event` start/stop, `maintenance_flag` on signature change | Rotating equipment, condition monitoring |
| `esp32-optical-counter` | Cycles via reflective/slot sensor | `event` cycle_complete | Sewing machines, presses, anything with a visible repeating motion |

All three share the same base firmware, provisioning flow, and gateway integration. Hardware designs (KiCad, BOM, enclosure STLs) live in `retrofit/{kit}/hardware/`; total parts cost per node is roughly $12 to $20 depending on sourcing.

## 2. Build or Buy the Node

Each kit's `hardware/BOM.md` lists exact parts with typical sources (AliExpress part numbers included, and Dhaka-relevant local sources where community-verified). The short version for the CT clamp kit:

- ESP32 dev board (ESP32-WROOM-32, not the -C3 minimal boards)
- SCT-013 series split-core CT (size to the machine's breaker - 30 A for single sewing machines, 100 A for dye machine mains)
- Burden/bias circuit per the schematic (3 resistors, 1 capacitor, or the ready-made module listed)
- 5 V supply (a quality phone charger is fine; the no-name ones are the top field failure)
- Enclosure - the printable STL, or any IP54 junction box

Solder-free assembly using the listed screw-terminal breakout is fully supported and recommended for first builds.

## 3. Flash the Firmware

```bash
cd retrofit/esp32-ct-clamp/firmware
pip install platformio
pio run -t upload    # board connected via USB
```

Prebuilt binaries for each release are on the GitHub Releases page if you prefer a GUI flasher (instructions in `firmware/FLASHING.md`).

## 4. Provision

On first boot the node opens a WiFi access point `omp-setup-XXXX`. Connect with a phone, browse to `192.168.4.1`, and enter:

- Factory WiFi SSID/password (2.4 GHz only)
- Gateway address (the Pi's IP) and the node's assigned `machine_id`
- For CT kits - the CT rating (e.g. 30 A/1 V) and mains voltage/phases, so kWh math is right

The node then joins the factory network and announces itself to the gateway over local MQTT. Provisioning details, including bulk provisioning 20+ nodes from a CSV, are in `firmware/PROVISIONING.md`.

## 5. Install at the Machine

### CT clamp (electrician's section)

1. Machine locked out, panel opened per facility procedure.
2. Clamp around **one phase conductor only** (never around a cable containing line and neutral together - fields cancel and you read zero).
3. For 3-phase machines, one clamp on one phase with `phases: 3` configured gives a serviceable estimate; three clamps into one node (supported, 3 ADC channels) gives accuracy. Start with one; upgrade the nodes on machines where energy attribution matters most (dye machines).
4. Route the CT lead out of the panel away from contactors, node mounted outside the panel, panel closed, lockout removed.

### Vibration

Mount magnetically or bolt to the bearing housing or frame near the main motor, cable-tied lead, node within 2 m. Orientation noted in config.

### Optical counter

Aim the sensor at the repeating element (needle bar, flywheel mark, press ram), adjust the trim pot until the onboard LED blinks once per cycle, then lock the pot with a drop of nail polish. This 5-minute alignment is the entire calibration.

## 6. Register With the Gateway

Retrofit nodes appear to the gateway through the `retrofit-esp32` adapter. In `/etc/omp/registry.yaml`:

```yaml
machines:
  - machine_id: f1-line1-m03
    adapter: retrofit-esp32
    config:
      node_id: omp-node-3f2a        # printed by the provisioning page
      kit: ct_clamp
    location: { site: f1, area: sewing, line: line1, station: m03 }
```

Restart the gateway and verify exactly as in [First Real Machine](../getting-started/first-real-machine.md) section 6 - status `ok`, no dead letters, seq persistence. Note the emitted `data_source` is `retrofit`, and downstream consumers will correctly weight it as such (see the honesty ladder in the schema spec).

## 7. Validating the Data Is True

Retrofit data is inferred, so validate the inference on day one:

- **CT clamp** - run the machine through a known cycle; confirm start/stop events match reality and the kWh over an hour is plausible against the machine's nameplate. If idle draw reads as "running", raise `load_threshold_w` in the node config.
- **Optical counter** - count 50 cycles manually against the emitted count. Off by a consistent factor of 2? The mark passes the sensor twice per cycle; set `divisor: 2`.
- **Vibration** - capture a week of baseline before trusting any `maintenance_flag`; the firmware's signature detection needs that baseline period.

## 8. Fleet Practicalities

- One gateway comfortably handles 100+ retrofit nodes; the constraint is WiFi, not the gateway. Use a dedicated 2.4 GHz SSID/VLAN for nodes, not the office WiFi.
- Label every node physically with its `machine_id`. Future you, at machine 60, will be grateful.
- Node firmware updates are OTA from the gateway (`omp-gateway retrofit-update`), staged and rollback-safe.
- Expected failure modes in year one - power supplies (keep spares), WiFi drops during compressor starts (nodes buffer 10 minutes locally and replay), and clamps knocked loose during machine maintenance (a `machine.json` re-emit with a maintenance note is good practice after any panel work).

## Troubleshooting

| Symptom | Usual cause |
|---|---|
| Node visible in provisioning, never reaches gateway | 5 GHz-only SSID, captive portal, or client isolation on the factory AP |
| Energy reads zero, machine clearly running | Clamp around line+neutral together, or clamp not fully closed |
| Energy reads absurdly high | CT rating mismatch in config (30 A clamp configured as 100 A) |
| Counts drift high on optical | Sensor catching a second reflection - narrow the aim, add the supplied aperture sticker |
| Node reboots under load | Inadequate power supply - replace the charger first, always |
