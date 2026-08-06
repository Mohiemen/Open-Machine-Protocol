"""omp-gateway CLI.

Shipped in M2 Phase 1: `run-once` (drive one adapter against a dev config and
print validated envelopes - the adapter development loop from the
Writing an Adapter guide) and `dead-letters`. Service management
(install-service, status, tail, signing) is M2 Phase 2 - see gateway/README.md.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import tempfile
import threading

import yaml

from . import __version__
from .adapter import AdapterBase
from .core.engine import Engine
from .core.store import Store
from .exporters.base import StdoutExporter


def load_adapter_class(adapter_path: str):
    """Import adapter.py (or an __init__.py package) from a directory path
    and return its Adapter class."""
    p = pathlib.Path(adapter_path).resolve()
    candidates = [p / "adapter.py", p / "__init__.py", p]
    src = next((c for c in candidates if c.is_file()), None)
    if src is None:
        raise SystemExit(f"no adapter module found under {adapter_path}")
    spec = importlib.util.spec_from_file_location(f"omp_adapter_{p.stem}", src)
    module = importlib.util.module_from_spec(spec)
    # let adapter.py import its sibling protocol.py (the layout the
    # Writing an Adapter guide recommends); every adapter names that module
    # "protocol", so evict this adapter's siblings from sys.modules after
    # exec to keep two adapters from sharing one cached module
    sys.path.insert(0, str(src.parent))
    before = set(sys.modules)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(src.parent))
        for name in set(sys.modules) - before:
            mod_file = getattr(sys.modules[name], "__file__", None) or ""
            if mod_file.startswith(str(src.parent)):
                del sys.modules[name]
    cls = getattr(module, "Adapter", None)
    if cls is None or not issubclass(cls, AdapterBase):
        raise SystemExit(f"{src} does not define an Adapter(AdapterBase) class")
    return cls


def cmd_run_once(args) -> int:
    config = yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8"))
    machine_id = config.get("machine_id", "dev-machine-01")
    cls = load_adapter_class(args.adapter)
    adapter = cls(config=config.get("config", {}))

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(pathlib.Path(args.state_dir or tmp) / "buffer.db")
        engine = Engine(args.gateway_id, store, args.spec_dir)
        exporter = StdoutExporter()
        stop_evt = threading.Event()

        def emit(body):
            envelope = engine.process(machine_id, body)
            if envelope is not None:
                exporter.drain(store)

        thread = threading.Thread(target=adapter.start, args=(emit,), daemon=True)
        thread.start()
        try:
            stop_evt.wait(args.duration)
        except KeyboardInterrupt:
            pass
        adapter.stop()
        thread.join(timeout=10)
        exporter.drain(store)
        dead = store.dead_letters()
        if dead:
            print(f"# {len(dead)} dead-lettered message(s):", file=sys.stderr)
            for d in dead:
                print(f"#   {d['machine_id']} {d['received_ts']}: {d['error']}",
                      file=sys.stderr)
            return 1
        store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omp-gateway", description=__doc__)
    parser.add_argument("--version", action="version",
                        version=f"omp-gateway {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run-once",
                           help="drive one adapter, print validated envelopes")
    p_run.add_argument("--adapter", required=True,
                       help="path to the adapter directory")
    p_run.add_argument("--config", required=True, help="dev config YAML")
    p_run.add_argument("--duration", type=float, default=10.0,
                       help="seconds to run (default 10)")
    p_run.add_argument("--gateway-id", default="gw-dev-01")
    p_run.add_argument("--state-dir", default=None,
                       help="persist seq/buffer here instead of a temp dir")
    p_run.add_argument("--spec-dir", default=None)
    p_run.set_defaults(func=cmd_run_once)

    p_ins = sub.add_parser("install-service",
                           help="create state dirs, keypair, registry template; "
                                "print the systemd unit")
    p_ins.add_argument("--prefix", default="/etc/omp",
                       help="config directory (default /etc/omp)")
    p_ins.add_argument("--state-dir", default="/var/lib/omp")
    p_ins.add_argument("--gateway-id", default=None,
                       help="default: gw-<hostname>")
    p_ins.set_defaults(func=cmd_install)

    p_id = sub.add_parser("show-identity", help="print gateway_id and pubkey")
    p_id.add_argument("--prefix", default="/etc/omp")
    p_id.add_argument("--state-dir", default="/var/lib/omp")
    p_id.set_defaults(func=cmd_show_identity)

    p_daemon = sub.add_parser("run", help="run the gateway from a registry")
    p_daemon.add_argument("--registry", required=True)
    p_daemon.add_argument("--state-dir", required=True)
    p_daemon.add_argument("--adapters-dir", default="adapters",
                          help="directory containing adapter packages by name")
    p_daemon.add_argument("--gateway-id", default=None,
                          help="default: from <state-dir>/gateway_id")
    p_daemon.add_argument("--sign", action="store_true",
                          help="sign envelopes with <state-dir>/keys/gateway.pem "
                               "(created if absent)")
    p_daemon.add_argument("--duration", type=float, default=None,
                          help="run for N seconds then exit (default: forever)")
    p_daemon.add_argument("--spec-dir", default=None)
    p_daemon.set_defaults(func=cmd_run)

    p_st = sub.add_parser("status", help="report machines, buffer, dead letters")
    p_st.add_argument("--state-dir", required=True)
    p_st.set_defaults(func=cmd_status)

    p_dl = sub.add_parser("dead-letters", help="print recent dead letters")
    p_dl.add_argument("--state-dir", required=True)
    p_dl.add_argument("--limit", type=int, default=20)
    p_dl.set_defaults(func=cmd_dead_letters)

    args = parser.parse_args(argv)
    return args.func(args)


SYSTEMD_UNIT = """\
[Unit]
Description=Open Machine Protocol gateway
After=network-online.target

[Service]
User=omp
ExecStart={exe} run --registry {prefix}/registry.yaml --state-dir {state} --sign
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def cmd_install(args) -> int:
    from .core.keys import GatewayKey

    prefix = pathlib.Path(args.prefix)
    state = pathlib.Path(args.state_dir)
    (prefix / "maps").mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    gateway_id = args.gateway_id or f"gw-{__import__('socket').gethostname().lower()}"
    (state / "gateway_id").write_text(gateway_id + "\n", encoding="utf-8")
    registry = prefix / "registry.yaml"
    if not registry.exists():
        registry.write_text("machines: []\n", encoding="utf-8")
    key = GatewayKey.load_or_generate(state / "keys" / "gateway.pem")
    print(f"gateway_id: {gateway_id}")
    print(f"pubkey: ed25519:{key.public_key_b64()}")
    print("# record both in your key registry now (DPP Evidence Chain s6)")
    print("# systemd unit (write to /etc/systemd/system/omp-gateway.service):")
    print(SYSTEMD_UNIT.format(exe=sys.argv[0], prefix=prefix, state=state))
    return 0


def cmd_show_identity(args) -> int:
    from .core.keys import GatewayKey

    state = pathlib.Path(args.state_dir)
    gateway_id = (state / "gateway_id").read_text(encoding="utf-8").strip()
    key = GatewayKey.load(state / "keys" / "gateway.pem")
    print(f"gateway_id: {gateway_id}")
    print(f"pubkey: ed25519:{key.public_key_b64()}")
    return 0


def cmd_status(args) -> int:
    store = Store(pathlib.Path(args.state_dir) / "buffer.db")
    snap = store.snapshot()
    print(f"machines: {len(snap['machines'])}  buffered: {snap['buffered']}  "
          f"dead_letters: {snap['dead_letters']}")
    for machine_id, seq in sorted(snap["machines"].items()):
        print(f"  {machine_id}  seq {seq}")
    for exporter, rowid in sorted(snap["cursors"].items()):
        print(f"  exporter {exporter} at row {rowid}")
    store.close()
    return 0


def cmd_dead_letters(args) -> int:
    store = Store(pathlib.Path(args.state_dir) / "buffer.db")
    dead = store.dead_letters(args.limit)
    for d in dead:
        print(f"{d['received_ts']}  {d['machine_id']}  {d['error']}")
    store.close()
    return 1 if dead else 0


def cmd_run(args) -> int:
    """The gateway daemon: registry -> adapters -> engine -> exporters."""
    from .adapter import now_iso
    from .core.registry import load_registry

    state = pathlib.Path(args.state_dir)
    registry = load_registry(args.registry)
    gateway_id = args.gateway_id
    if gateway_id is None:
        id_file = state / "gateway_id"
        gateway_id = (id_file.read_text(encoding="utf-8").strip()
                      if id_file.exists() else "gw-unnamed-01")
    signer = None
    if args.sign:
        from .core.keys import GatewayKey

        signer = GatewayKey.load_or_generate(state / "keys" / "gateway.pem")

    store = Store(state / "buffer.db")
    engine = Engine(gateway_id, store, args.spec_dir, signer=signer)
    exporters = _build_exporters(registry)
    drain_lock = threading.Lock()

    def drain():
        with drain_lock:
            for exporter in exporters:
                exporter.drain(store)

    threads = []
    stop_evt = threading.Event()
    for m in registry.get("machines", []):
        adapter_dir = pathlib.Path(args.adapters_dir) / m["adapter"]
        cls = load_adapter_class(str(adapter_dir))
        adapter = cls(config=m["config"])
        machine_id = m["machine_id"]
        # machine announcement on startup (spec 7.1)
        try:
            info = adapter.probe(m["config"])
            engine.process(machine_id, adapter.body(
                schema="machine",
                profile=m.get("profile", (cls.supported_profiles or ["generic/0.1"])[0]),
                body={
                    "machine_class": info.machine_class,
                    **({"make": info.make} if info.make else {}),
                    **({"model": info.model} if info.model else {}),
                    "location": m.get("location", {"site": "unknown"}),
                    "capabilities": info.capabilities,
                    "adapter": {"name": cls.name, "version": cls.version},
                    "data_source": info.data_source,
                },
                event_ts=now_iso(),
            ))
        except Exception as exc:  # noqa: BLE001 - machine marked failed, others continue
            print(f"# probe failed for {machine_id}: {exc}", file=sys.stderr)
            continue

        def emit(body, _mid=machine_id):
            engine.process(_mid, body)
            drain()

        t = threading.Thread(target=adapter.start, args=(emit,), daemon=True,
                             name=f"adapter-{machine_id}")
        t.start()
        threads.append((adapter, t))

    drain()
    try:
        stop_evt.wait(args.duration)
    except KeyboardInterrupt:
        pass
    for adapter, _ in threads:
        adapter.stop()
    for _, t in threads:
        t.join(timeout=10)
    drain()
    store.close()
    return 0


def _build_exporters(registry: dict):
    from .exporters.base import StdoutExporter

    configured = registry.get("exporters", [])
    if not configured:
        return [StdoutExporter()]
    built = []
    for e in configured:
        if e["type"] == "stdout":
            built.append(StdoutExporter())
        elif e["type"] == "mqtt":  # pragma: no cover - needs a broker
            import re as _re

            from .exporters.mqtt import MqttExporter

            m = _re.fullmatch(r"mqtt://([^:/]+)(?::(\d+))?", e["broker"])
            if not m:
                raise SystemExit(f"bad broker URL {e['broker']!r}")
            locations = {mach["machine_id"]: mach.get("location", {})
                         for mach in registry.get("machines", [])}
            built.append(MqttExporter(m.group(1), int(m.group(2) or 1883),
                                      e.get("topic_prefix", "omp"),
                                      locations=locations))
        else:
            raise SystemExit(f"unsupported exporter type {e['type']!r} "
                             "(REST/OPC UA/CSV are roadmap)")
    return built


if __name__ == "__main__":
    sys.exit(main())
