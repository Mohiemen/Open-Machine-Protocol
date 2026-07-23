# Your First Real Machine

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/getting-started/first-real-machine.md |
| **You need** | One machine with either a Modbus interface or a documented serial output, a Raspberry Pi 4/5 (2 GB+) or any small Linux box, a competent afternoon |
| **Before this** | Do the [Quickstart](quickstart.md) on your laptop first - it teaches the concepts this guide assumes |

---

## 1. Pick Your Path

| Your machine has... | Path | Section |
|---|---|---|
| A Modbus RTU (RS485) or Modbus TCP interface | `generic-modbus` + a register map | 4 |
| A documented RS232/RS485 serial output | `generic-serial` + a line profile | 5 |
| An unsupported network protocol | Check `adapters/` for a vendor adapter; else capture traffic and open an issue | [Reverse-engineering guide](../guides/reverse-engineering-protocols.md) |
| No digital output at all | ESP32 retrofit kit | [Retrofit guide](../guides/retrofit-installation.md) |

Not sure what your machine has? Photograph the controller's rear panel and its manual's "communication" pages and ask in Discussions - identification-by-photo is a common and welcome question.

## 2. Prepare the Gateway Device

On a fresh Raspberry Pi OS Lite (64-bit) or Debian/Ubuntu:

```bash
sudo apt update && sudo apt install -y python3.11-venv git
git clone https://github.com/Mohiemen/Open-Machine-Protocol
cd omp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ./gateway -e ./tools

sudo omp-gateway install-service   # systemd unit, keypair generation, dirs
```

`install-service` creates:

- `/etc/omp/registry.yaml` - your machine registry (starts empty)
- `/var/lib/omp/` - buffer, keys, dead letters
- The gateway keypair. **Record the public key now** - `omp-gateway show-identity` prints `gateway_id` and pubkey; these go into your key registry (see the [DPP Evidence Chain](../integrations/dpp-evidence-chain.md), section 6, if verifiability matters to you later - it's much easier to do this bookkeeping from day one).

## 3. Physical Connection Safety

- **Never wire anything with the machine running.** Lockout applies to data cabling too - a slipped RS485 lead across the wrong terminals can end a controller board.
- RS485 - twisted pair, A to A, B to B (vendors disagree on labeling; if it doesn't work, swap them - it's the single most common issue), termination resistor only at the two bus ends.
- USB serial adapters - use FTDI or CP210x chips; the no-name ones cause mysterious grief. Note the device path (`ls /dev/ttyUSB*` before and after plugging).
- Keep data cables away from motor power lines and VFD output cables; parallel runs induce noise. Cross at right angles where crossing is unavoidable.
- Ethernet machines - put the gateway on the same OT subnet; do not bridge the machine network to the office network to make this work. See the [Hardening Guide](../security/hardening-guide.md) for proper topology.

## 4. Path A - Modbus

### 4.1 Find the register map

The machine manual's Modbus appendix, or the vendor's separate comms manual, lists registers - e.g. "40021 = spindle speed, u16, RPM". If you can't find documentation, `omp-sniff --modbus-scan` can probe common register ranges read-only and show you what responds with plausible values.

### 4.2 Write the mapping file

`/etc/omp/maps/mymachine.yaml`:

```yaml
device: overlock-station-4
profile: textile-sewing/0.1
machine_class: overlock
poll_interval_ms: 1000
registers:
  - address: 40021          # holding register
    name: cycle_count
    type: u16
    emit:
      schema: event
      event_type: cycle_complete
      mode: on_increment     # emit when the value increases
      payload_field: cycle_count
  - address: 40035
    name: machine_state
    type: u16
    emit:
      schema: event
      event_type: state_change
      mode: on_change
      enum: { 0: idle, 1: running, 2: fault }
  - address: 40102
    name: motor_current
    type: u16
    scale: 0.1               # register is deciamps
    emit:
      schema: telemetry
      channel: motor_current
      unit: A
      mode: stats            # gateway aggregates to 60 s stats blocks
```

The three `mode` values (`on_increment`, `on_change`, `stats`) cover the overwhelming majority of Modbus devices with zero code.

### 4.3 Register the machine

Append to `/etc/omp/registry.yaml`:

```yaml
machines:
  - machine_id: f1-line2-overlock04
    adapter: generic-modbus
    config:
      port: /dev/ttyUSB0     # or host: 192.168.10.31 for Modbus TCP
      baud: 9600
      unit_id: 1
      mapping_file: /etc/omp/maps/mymachine.yaml
    location: { site: f1, area: sewing, line: line2, station: st04 }
```

## 5. Path B - Serial

For controllers that print lines like `CYCLE 1042` or `T=060.5 PH=05.2`:

```yaml
machines:
  - machine_id: f1-dye-jig01
    adapter: generic-serial
    config:
      port: /dev/ttyUSB0
      baud: 9600
      line_profile: /etc/omp/maps/jig01-lines.yaml
    location: { site: f1, area: dyeing, line: jigs, station: jig01 }
```

The line profile maps regex patterns to emissions:

```yaml
profile: textile-dyeing/0.1
machine_class: jigger
patterns:
  - match: '^TEMP=(?P<c>\d+\.\d)$'
    emit: { schema: telemetry, channel: bath_temp, unit: Cel, value: c, mode: stats }
  - match: '^PHASE (?P<name>\w+) START$'
    emit: { schema: event, event_type: phase_start, payload: { phase: name } }
```

Don't know the output format? Watch it raw first: `omp-sniff --serial /dev/ttyUSB0 --baud 9600` while the machine runs a cycle, and the patterns usually write themselves.

## 6. Start and Verify

```bash
sudo systemctl start omp-gateway
omp-gateway status
# gateway: gw-f1-pilot-01  uptime 00:00:41
# f1-line2-overlock04  generic-modbus  ok  last data 2s ago  seq 38

# Watch the live stream locally
omp-gateway tail | omp-validate
```

Run the machine through a real cycle and confirm you see the events you mapped. Then check the three health signals that matter:

1. `omp-gateway status` shows `ok`, not `degraded` (degraded on serial usually means noise - reseat, check grounding, shorten the cable).
2. `omp-gateway dead-letters` is empty (entries mean your mapping emits something non-conformant - the stored validation error says exactly what).
3. `seq` climbs without resets across a `systemctl restart omp-gateway` (persistence working).

## 7. Export Somewhere

Add to `registry.yaml` and restart:

```yaml
exporters:
  - type: mqtt
    broker: mqtt://192.168.10.5:1883
    topic_prefix: omp
```

Your quickstart Grafana stack, pointed at this broker, now shows a real machine. Same dashboard, zero changes - that was the promise.

## 8. What Good Looks Like After a Week

- Buffer disk usage stable (check `omp-gateway status --verbose`)
- Reconnect count low and correlated with known events (compressor starts, power dips)
- No dead letters, or only understood ones
- A power cut happened and you lost nothing - the buffer replayed on boot

When those hold, you're ready to add machines 2 through 50, which is mostly copy-paste in the registry. At around 10 machines, read [Factory Deployment](../guides/factory-deployment.md) for network layout, and consider a UPS for the gateway if you haven't already - in most factories this is not optional.

## Common First-Day Problems

| Symptom | Usual cause |
|---|---|
| No data, adapter `disconnected` | Wrong port path, A/B swapped on RS485, wrong baud |
| Data flows, values are garbage | Wrong register type (u16 vs s16 vs float pairs), wrong scale, byte order - try `type: u16_swapped` |
| Works for hours then dies until reboot | Cheap USB adapter or power brownouts - powered hub, better PSU, UPS |
| Dead letters on every message | Mapping emits a field the profile doesn't define - the validation error names it |
| seq resets after restart | `/var/lib/omp` not persisted (SD card issue, or you're running two gateway instances - don't) |
