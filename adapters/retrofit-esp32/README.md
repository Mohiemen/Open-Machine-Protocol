# retrofit-esp32

Gateway-side adapter for OMP retrofit nodes
([retrofit/esp32-ct-clamp](../../retrofit/esp32-ct-clamp/)). Subscribes to
`omp-node/{node_id}` on the local broker and translates node JSON into OMP
bodies:

| Node message | Becomes |
|---|---|
| `energy` (integral Wh) | `energy` body, metric `wh`, `source: ct_clamp` |
| `event` start/stop | core `start`/`stop` events, reason `load_threshold` |
| `hello` with a nonzero offline-drop counter | `maintenance_flag` (`node_dropped_messages`) - node-side loss is surfaced, never silent |

Identity: `probe()` reports `data_source: retrofit` with the node id as
serial, so downstream consumers weight the evidence per the honesty ladder.

- **Maintainer**: core maintainers (seeking a hardware-owning co-maintainer)
- **Dev/CI**: `messages` (injected list) or `replay_file` (NDJSON) drive the
  full path without a node; real mode needs paho-mqtt.
- **Soak declaration**: replay-tested only; the node firmware itself is a
  draft untested on hardware - see the retrofit README before deploying.
