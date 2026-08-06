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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
