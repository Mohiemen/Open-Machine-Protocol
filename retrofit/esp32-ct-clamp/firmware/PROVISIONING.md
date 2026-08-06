# Provisioning

**Status: DRAFT - untested on hardware.**

On first boot (or with BOOT held at power-up) the node opens WiFi AP
`omp-setup-XXXX` (last 4 hex digits of its id). Connect with a phone,
browse to `http://192.168.4.1`, and fill in:

| Field | Meaning |
|---|---|
| WiFi SSID / password | The factory's 2.4 GHz node SSID (dedicated VLAN per the hardening guide) |
| Gateway broker IP | The gateway's local MQTT broker |
| machine_id | The station id this node is attached to (matches the gateway registry) |
| CT rating (A) | The SCT-013 variant, e.g. 30 for 30A/1V |
| Mains voltage / phases | For the watts/kWh math; one clamp on one phase of a 3-phase machine with `phases=3` gives a serviceable estimate |
| Load threshold (W) | Above = machine running; tune if idle draw reads as running |

After save the node reboots, joins the network, and announces itself as
`omp-node-XXXX` on `omp-node/{node_id}` - that node id goes into the
gateway registry (`adapter: retrofit-esp32`, `config: {node_id: ...}`).

Bulk provisioning from CSV (20+ nodes) is a planned addition - contributions
welcome; the config surface above is the full field set it would need.
