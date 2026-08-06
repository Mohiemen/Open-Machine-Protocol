# Quickstart - A Live Factory Floor in 15 Minutes, No Hardware

| | |
|---|---|
| **Status** | Draft |
| **Location** | docs/getting-started/quickstart.md |
| **You need** | A laptop with Python 3.11+, 15 minutes. No machines, no Raspberry Pi, no cloud account. |
| **You get** | A simulated 10-machine sewing line streaming standardized, verifiable data into a live dashboard, and an understanding of every moving part. |

---

## 1. Install

```bash
git clone https://github.com/Mohiemen/Open-Machine-Protocol
cd Open-Machine-Protocol
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ./gateway -e ./tools
```

Check it worked:

```bash
omp-validate --version
omp-simulate --version
```

## 2. Your First OMP Messages (2 minutes)

Generate one simulated sewing machine and look at what comes out:

```bash
omp-simulate --profile textile-sewing --machines 1 --duration 10s
```

You'll see NDJSON envelopes scroll past. Grab one and read it:

```json
{
  "omp_version": "0.1.0",
  "profile": "textile-sewing/0.1",
  "gateway_id": "gw-sim-01",
  "machine_id": "sim-line1-m01",
  "seq": 14,
  "ts": "2026-07-24T10:02:11.408Z",
  "schema": "event",
  "body": {
    "event_type": "cycle_complete",
    "payload": { "cycle_count": 14, "cycle_time_ms": 31240 }
  },
  "checksum": "9f2a...\u2026"
}
```

Three things to notice, because they are the whole idea:

- **`profile`** tells any consumer exactly which vocabulary this machine speaks.
- **`seq`** increments by one per message per machine. A consumer that sees 14 then 16 knows message 15 exists and is missing. Completeness is checkable.
- **`checksum`** commits the body. Alter one digit of `cycle_count` and the message provably no longer matches. Integrity is checkable.

## 3. Validate the Stream (1 minute)

Pipe the simulator through the validator, which checks every envelope against the core schema AND the textile-sewing profile:

```bash
omp-simulate --profile textile-sewing --machines 1 --duration 10s | omp-validate
# ✔ 47 messages valid (schema: event x45, machine x1, process_run x1)
```

Now prove validation actually bites - inject a corrupted stream:

```bash
omp-simulate --profile textile-sewing --machines 1 --duration 10s --chaos corrupt-fields | omp-validate
# ✖ seq 23: body.payload.cycle_time_ms expected number, got string
# ✖ seq 31: checksum mismatch
# 45 valid, 2 invalid (details above)
```

In a real gateway those two messages would land in the dead-letter store, never exported as valid data. Nothing invalid travels silently.

## 4. Stream Into a Broker and Watch Live (5 minutes)

Start a local MQTT broker (any of these):

```bash
# Option A - Docker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf

# Option B - installed natively (Debian/Ubuntu: apt install mosquitto mosquitto-clients)
mosquitto -v
```

Now run a full 10-machine simulated line, exported over MQTT with proper topic structure:

```bash
omp-simulate --profile textile-sewing --machines 10 --export mqtt://localhost:1883 --site demo --line line1
```

In a second terminal, watch the floor come alive:

```bash
mosquitto_sub -t 'omp/#' -v
```

You are looking at the exact wire format a real factory produces. Topics follow `omp/{site}/{area}/{line}/{machine}/{schema}` - subscribe narrowly (`omp/demo/+/line1/+/event`) the way a platform would.

## 5. A Dashboard (5 minutes)

```bash
cd examples/grafana-dashboards
docker compose up -d      # Grafana + MQTT datasource, preconfigured
```

Open http://localhost:3000 (admin/admin), and the **Sewing Line Overview** dashboard shows live cycle counts, machine states, stop reasons, and per-machine cycle time distributions from your simulated line.

This dashboard consumes nothing but standard OMP messages. Point it at a real gateway later and it works unchanged. That is what a standard buys.

## 6. What You Just Learned, Mapped to Real Deployment

| In this quickstart | In a real factory |
|---|---|
| `omp-simulate` | The gateway on a Raspberry Pi, running adapters against machines |
| Simulated machines | Juki networks, Modbus PLCs, ESP32 retrofit nodes |
| `--chaos corrupt-fields` | Electrical noise, flaky serial lines, adapter bugs |
| Local Mosquitto | The factory's broker, or direct REST push to a platform |
| Grafana example | Your MES, factory OS, or DPP platform ingesting the same topics |

The envelope, topics, validation behavior, and dedup rules are identical. Nothing about the simulator is a toy format.

## 7. Where to Go Next

- **Have a real machine?** [Your First Real Machine](first-real-machine.md) walks through connecting one via generic-serial or a Modbus register map, including the gateway install on a Pi.
- **Machine has no digital output at all?** [Retrofit Installation](../guides/retrofit-installation.md) - the ESP32 CT clamp goes from parts to streaming in an afternoon.
- **Building a platform?** [Platform Ingestion](../integrations/platform-ingestion.md) - dedup, gap tracking, and the [DPP Evidence Chain](../integrations/dpp-evidence-chain.md).
- **Want to contribute?** [CONTRIBUTING.md](../../CONTRIBUTING.md) - and if you have access to an unsupported machine, a protocol capture is the most valuable thing you can give the project without writing code.

## Troubleshooting

- `omp-simulate: command not found` - the venv isn't active, or `pip install -e ./tools` failed; rerun and read its output.
- MQTT connection refused - broker not running or port 1883 taken; `docker logs mosquitto` or try `-p 1884:1883` and adjust the URL.
- Grafana shows no data - confirm messages flow (`mosquitto_sub -t 'omp/#'`), then check the datasource points at `host.docker.internal:1883` (Linux users - see the compose file's commented network_mode line).
- Anything else - [FAQ](faq.md), then GitHub Discussions. Include your OS and the exact command.
