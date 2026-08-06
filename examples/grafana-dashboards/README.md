# grafana-dashboards

The quickstart's dashboard stack: Mosquitto + Grafana with the Grafana Labs
MQTT datasource plugin, provisioned to subscribe to the OMP topic tree.

```bash
docker compose up -d
# then, from the repo root:
omp-simulate --profile textile-sewing --machines 10 --duration 8h \
  --export mqtt://localhost:1883 --site demo --line line1
```

Open http://localhost:3000 (admin/admin) → OMP → **Sewing Line Overview**.

Point it at a real gateway later by exporting to the same broker - the
dashboard consumes nothing but standard OMP topics
(`omp/{site}/{area}/{line}/{machine}/{schema}`), so it works unchanged.
That is what a standard buys.

**Status: community-verify wanted.** This compose stack is structurally
standard but has not been visually verified in CI (no browser there). The
MQTT datasource renders live messages; the richer derived panels the
quickstart describes (cycle-time distributions, stop-reason breakdowns)
need a persisting datasource - the honest architecture for that is the
[platform-ingest-reference](../platform-ingest-reference/) consumer landing
envelopes in a database Grafana queries, which is exactly the
platform-does-derivation split the docs prescribe. Screenshots and panel
improvements from anyone running this are a welcome first contribution
(`good first issue`).

Troubleshooting is in [quickstart section 5](../../docs/docs/getting-started/quickstart.md)
- most empty-panel cases are the Linux `host.docker.internal` note in the
compose file.
