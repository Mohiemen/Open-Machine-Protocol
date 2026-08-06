"""omp-gateway CLI.

Shipped in M2 Phase 1: `run-once` (drive one adapter against a dev config and
print validated envelopes - the adapter development loop from the
Writing an Adapter guide) and `dead-letters`. Service management
(install-service, status, tail, signing) is M2 Phase 2 - see gateway/README.md.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import signal
import sys
import tempfile
import threading
import time

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
    p_daemon.add_argument("--retention-days", type=float, default=30,
                          help="prune delivered envelopes older than this "
                               "(default 30, per the glossary)")
    p_daemon.add_argument("--max-buffer-bytes", type=int, default=None,
                          help="also prune delivered envelopes when the buffer "
                               "database exceeds this size")
    p_daemon.add_argument("--prune-interval", type=float, default=3600,
                          help="seconds between retention passes (default 1h)")
    p_daemon.add_argument("--max-crashes", type=int, default=5,
                          help="mark a machine failed after this many adapter "
                               "crashes (default 5)")
    p_daemon.add_argument("--probe-timeout", type=float, default=30,
                          help="seconds a probe() may take before the machine "
                               "is marked failed (default 30)")
    p_daemon.set_defaults(func=cmd_run)

    p_rl = sub.add_parser("reload",
                          help="tell a running gateway to re-read its registry")
    p_rl.add_argument("--state-dir", required=True)
    p_rl.set_defaults(func=cmd_reload)

    p_st = sub.add_parser("status", help="report machines, buffer, dead letters")
    p_st.add_argument("--state-dir", required=True)
    p_st.set_defaults(func=cmd_status)

    p_dl = sub.add_parser("dead-letters", help="print recent dead letters")
    p_dl.add_argument("--state-dir", required=True)
    p_dl.add_argument("--limit", type=int, default=20)
    p_dl.set_defaults(func=cmd_dead_letters)

    args = parser.parse_args(argv)
    return args.func(args)


def _supervise(adapter, emit, machine_id: str, stop_evt, max_crashes: int) -> None:
    """Adapter restart policy (Adapter Plugin API s6).

    An exception escaping start() is the adapter's failure, never the
    gateway's: catch it, count it in health, back off exponentially (1 s to
    5 min), and retry. After `max_crashes` the machine is marked `failed` and
    left alone - a crash-looping adapter that keeps re-opening a serial port
    is worse than one that stops and says so.
    """
    crashes = 0
    while not stop_evt.is_set():
        try:
            adapter.start(emit)
            return                      # returned cleanly: it is done
        except Exception as exc:        # noqa: BLE001 - isolation is the point
            crashes += 1
            if crashes >= max_crashes:
                adapter._mark_failed(
                    f"stopped after {crashes} crashes; last: {exc}")
                print(f"# {machine_id}: adapter failed after {crashes} crashes "
                      f"({exc}) - not retrying", file=sys.stderr)
                return
            adapter._mark_disconnected(f"crash {crashes}: {exc}")
            delay = adapter.backoff()
            print(f"# {machine_id}: adapter crashed ({exc}); retry in {delay}s",
                  file=sys.stderr)
            if stop_evt.wait(delay):
                return


def _probe_with_timeout(adapter, config: dict, timeout_s: float):
    """probe() MUST complete or raise within the probe timeout (API s2).

    A probe that hangs on a dead serial port would otherwise stall startup for
    every other machine on the floor, so it runs on its own thread and the
    machine is marked failed if it overruns.
    """
    result: dict = {}

    def run():
        try:
            result["info"] = adapter.probe(config)
        except Exception as exc:        # noqa: BLE001
            result["error"] = exc

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise TimeoutError(f"probe did not return within {timeout_s}s")
    if "error" in result:
        raise result["error"]
    return result["info"]


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
    id_file, key_file = state / "gateway_id", state / "keys" / "gateway.pem"
    for f, what in ((id_file, "gateway id"), (key_file, "gateway keypair")):
        if not f.exists():
            print(f"no {what} at {f} - run 'omp-gateway install-service' "
                  f"(or 'run --sign') against this state dir first", file=sys.stderr)
            return 1
    key = GatewayKey.load(key_file)
    print(f"gateway_id: {id_file.read_text(encoding='utf-8').strip()}")
    print(f"pubkey: ed25519:{key.public_key_b64()}")
    return 0


def cmd_reload(args) -> int:
    """Signal a running gateway to re-read its registry (SIGHUP).

    Adding a machine should not drop every other adapter connection on the
    floor - the deployment guide expects one person to add 10-15 machines a
    day without restarts.
    """
    pidfile = pathlib.Path(args.state_dir) / "gateway.pid"
    if not pidfile.exists():
        print(f"no running gateway found ({pidfile} absent)", file=sys.stderr)
        return 1
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGHUP)
    except (ValueError, ProcessLookupError, PermissionError) as exc:
        print(f"could not signal gateway: {exc}", file=sys.stderr)
        return 1
    print(f"reload requested (pid {pid}); the gateway validates before "
          "applying and refuses an invalid registry")
    return 0


def cmd_status(args) -> int:
    store = Store(pathlib.Path(args.state_dir) / "buffer.db")
    snap = store.snapshot()
    print(f"machines: {len(snap['machines'])}  buffered: {snap['buffered']}  "
          f"dead_letters: {snap['dead_letters']}  "
          f"buffer_db: {snap['db_bytes'] // 1024} KiB")
    for machine_id, seq in sorted(snap["machines"].items()):
        print(f"  {machine_id}  seq {seq}")
    for exporter, rowid in sorted(snap["cursors"].items()):
        print(f"  exporter {exporter} at row {rowid}")
    for pr in snap["recent_prunes"]:
        print(f"  pruned {pr['rows']} envelope(s) at {pr['pruned_at']} "
              f"({pr['reason']})")
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
    id_file = state / "gateway_id"
    gateway_id = args.gateway_id
    if gateway_id is None:
        gateway_id = (id_file.read_text(encoding="utf-8").strip()
                      if id_file.exists() else "gw-unnamed-01")
    # persist the identity so show-identity works against this state dir even
    # when the gateway was started without install-service (the pubkey has to
    # be recordable in the key registry - DPP Evidence Chain section 6)
    state.mkdir(parents=True, exist_ok=True)
    current = id_file.read_text(encoding="utf-8").strip() if id_file.exists() else None
    if current != gateway_id:
        id_file.write_text(gateway_id + "\n", encoding="utf-8")
    signer = None
    if args.sign:
        from .core.keys import GatewayKey

        signer = GatewayKey.load_or_generate(state / "keys" / "gateway.pem")

    store = Store(state / "buffer.db")
    engine = Engine(gateway_id, store, args.spec_dir, signer=signer)
    exporters = _build_exporters(registry)
    drain_lock = threading.Lock()

    from .exporters.base import ExporterClosed

    stop_evt = threading.Event()

    def drain():
        """Returns False once a destination is gone for good - the caller
        stops rather than spinning on a closed pipe. Undelivered envelopes
        stay in the buffer unacked, so nothing is silently lost."""
        try:
            with drain_lock:
                for exporter in exporters:
                    exporter.drain(store)
        except ExporterClosed:
            stop_evt.set()
            return False
        return True
    running: dict[str, dict] = {}   # machine_id -> {adapter, thread, spec}

    def start_machine(m: dict) -> bool:
        """Probe, announce, and supervise one machine. False if it failed."""
        adapter_dir = pathlib.Path(args.adapters_dir) / m["adapter"]
        cls = load_adapter_class(str(adapter_dir))
        adapter = cls(config=m["config"])
        machine_id = m["machine_id"]
        try:
            info = _probe_with_timeout(adapter, m["config"], args.probe_timeout)
            # machine announcement on (re)start - spec 7.1
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
        except Exception as exc:  # noqa: BLE001 - this machine fails, others continue
            print(f"# probe failed for {machine_id}: {exc}", file=sys.stderr)
            return False

        def emit(body, _mid=machine_id, _adapter=adapter):
            engine.process(_mid, body)
            if not drain():
                _adapter.stop()   # destination gone; wind this adapter down

        t = threading.Thread(target=_supervise, daemon=True,
                             name=f"adapter-{machine_id}",
                             args=(adapter, emit, machine_id, stop_evt,
                                   args.max_crashes))
        t.start()
        running[machine_id] = {"adapter": adapter, "thread": t, "spec": m}
        return True

    def stop_machine(machine_id: str) -> None:
        entry = running.pop(machine_id, None)
        if entry:
            entry["adapter"].stop()
            entry["thread"].join(timeout=10)

    reload_requested = threading.Event()
    pidfile = state / "gateway.pid"
    pidfile.write_text(f"{os.getpid()}\n", encoding="utf-8")
    try:
        signal.signal(signal.SIGHUP, lambda *_: reload_requested.set())
    except (AttributeError, ValueError):   # no SIGHUP, or not the main thread
        pass

    def apply_reload() -> None:
        """Validate the new registry FULLY before touching anything.

        The deployment guide promises `reload` "validates before applying,
        refuses invalid" - an operator pulling a bad registry from git must
        not take the floor down. Machines whose config is unchanged keep
        streaming untouched, so their seq continuity is never broken.
        """
        try:
            new = load_registry(args.registry)
            for m in new.get("machines", []):
                adapter_dir = pathlib.Path(args.adapters_dir) / m["adapter"]
                load_adapter_class(str(adapter_dir))   # raises if missing/bad
        except Exception as exc:  # noqa: BLE001 - keep serving the old config
            print(f"# reload REFUSED, still running the previous registry: {exc}",
                  file=sys.stderr)
            return
        wanted = {m["machine_id"]: m for m in new.get("machines", [])}
        added = [mid for mid in wanted if mid not in running]
        removed = [mid for mid in running if mid not in wanted]
        changed = [mid for mid, m in wanted.items()
                   if mid in running and running[mid]["spec"] != m]
        for mid in removed:
            stop_machine(mid)
        for mid in changed:
            stop_machine(mid)
            start_machine(wanted[mid])
        for mid in added:
            start_machine(wanted[mid])
        untouched = len(running) - len(added) - len(changed)
        print(f"# reloaded: +{len(added)} -{len(removed)} ~{len(changed)}, "
              f"{max(untouched, 0)} untouched", file=sys.stderr)

    for m in registry.get("machines", []):
        start_machine(m)

    drain()
    exporter_names = [e.name for e in exporters]
    try:
        # tick so retention runs on a long-lived gateway; `--duration` runs
        # (tests, demos) fall out of the loop on the first pass
        deadline = None if args.duration is None else time.monotonic() + args.duration
        while not stop_evt.is_set():
            wait = args.prune_interval
            if deadline is not None:
                wait = min(wait, max(deadline - time.monotonic(), 0))
            if stop_evt.wait(wait):
                break
            if reload_requested.is_set():
                reload_requested.clear()
                apply_reload()
                continue
            if deadline is not None and time.monotonic() >= deadline:
                break
            result = store.prune(exporter_names,
                                 retention_days=args.retention_days,
                                 max_bytes=args.max_buffer_bytes)
            if result["pruned"]:
                print(f"# pruned {result['pruned']} delivered envelope(s): "
                      f"{result['reason']}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    for machine_id in list(running):
        stop_machine(machine_id)
    drain()
    pidfile.unlink(missing_ok=True)
    store.close()
    # if stdout is a closed pipe, Python's exit-time flush raises again -
    # point the fd at /dev/null so the process exits quietly like any other
    # well-behaved CLI in a pipeline
    try:
        sys.stdout.flush()
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
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
