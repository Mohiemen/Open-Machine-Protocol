"""generic-modbus: protocol frame vectors + full poll path via injected
transport (no PLC needed - the documented dev/CI mode)."""
import struct
import threading
import time

import pytest

from omp.cli import load_adapter_class
from omp.core.engine import Engine
from omp.core.store import Store

ADAPTER_DIR = "adapters/generic-modbus"
_spec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location(
    "generic_modbus_protocol", f"{ADAPTER_DIR}/protocol.py"
)
mb = __import__("importlib.util", fromlist=["util"]).module_from_spec(_spec)
_spec.loader.exec_module(mb)

MAPPING = """
device: overlock-station-4
profile: textile-sewing/0.1
machine_class: overlock
poll_interval_ms: 1
registers:
  - address: 40021
    name: cycle_count
    type: u16
    emit: { schema: event, event_type: cycle_complete, mode: on_increment, payload_field: cycle_count }
  - address: 40035
    name: machine_state
    type: u16
    emit:
      schema: event
      event_type: state_change
      mode: on_change
      enum: { 0: idle, 1: running, 2: fault }
"""


# ---------------------------------------------------------------- protocol
def test_tcp_roundtrip():
    req = mb.build_read_tcp(7, 1, mb.READ_HOLDING, 20, 1)
    tid, proto, length, unit = struct.unpack(">HHHB", req[:7])
    assert (tid, proto, unit) == (7, 0, 1)
    response = struct.pack(">HHHB", 7, 0, 5, 1) + bytes([3, 2, 0x01, 0x9A])
    assert mb.parse_read_tcp(response, 7, 3) == [410]


def test_rtu_crc_and_roundtrip():
    req = mb.build_read_rtu(1, mb.READ_HOLDING, 20, 1)
    assert mb.crc16(req[:-2]) == struct.unpack("<H", req[-2:])[0]
    body = bytes([1, 3, 2, 0x00, 0x2A])
    response = body + struct.pack("<H", mb.crc16(body))
    assert mb.parse_read_rtu(response, 1, 3) == [42]
    with pytest.raises(mb.ModbusError, match="CRC"):
        mb.parse_read_rtu(response[:-1] + b"\x00", 1, 3)


def test_exception_response_raises():
    response = struct.pack(">HHHB", 1, 0, 3, 1) + bytes([0x83, 0x02])
    with pytest.raises(mb.ModbusError, match="exception code 2"):
        mb.parse_read_tcp(response, 1, 3)


def test_addressing_and_decode():
    assert mb.resolve_address(40021) == (3, 20)
    assert mb.resolve_address(30007) == (4, 6)
    assert mb.decode_value([0xFFFF], "s16") == -1
    assert mb.decode_value([1, 0], "u32") == 65536
    assert mb.decode_value([123], "u16", scale=1) == 123


def test_no_write_functions_exist():
    """Constitutional: the protocol layer must not offer write frames."""
    assert not [n for n in dir(mb) if "write" in n.lower()]


# ---------------------------------------------------------------- full path
class FakePlc:
    """Answers TCP read-holding requests from a register dict; values can
    change between polls via the script."""

    def __init__(self, script):
        self.script = script  # list of {offset: value} dicts, one per poll
        self.poll = -1
        self.reads_this_poll = 0

    def __call__(self, request: bytes) -> bytes:
        tid, _, _, unit = struct.unpack(">HHHB", request[:7])
        func, offset, count = struct.unpack(">BHH", request[7:12])
        if self.reads_this_poll == 0:
            self.poll = min(self.poll + 1, len(self.script) - 1)
        self.reads_this_poll = (self.reads_this_poll + 1) % 2  # 2 registers/poll
        value = self.script[self.poll].get(offset, 0)
        pdu = bytes([func, 2]) + struct.pack(">H", value)
        return struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu


def test_poll_to_events_end_to_end(tmp_path):
    (tmp_path / "map.yaml").write_text(MAPPING, encoding="utf-8")
    script = [
        {20: 100, 34: 0},   # baseline poll - no events
        {20: 101, 34: 1},   # cycle +1, state idle->running
        {20: 101, 34: 1},   # nothing changed
        {20: 103, 34: 2},   # cycle increment, state running->fault
    ]
    cls = load_adapter_class(ADAPTER_DIR)
    adapter = cls(config={
        "mapping_file": str(tmp_path / "map.yaml"),
        "transport": FakePlc(script),
        "framing": "tcp",
        "max_polls": len(script),
    })
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    out = []

    def emit(body):
        env = engine.process("f1-line2-overlock04", body)
        out.append(env)

    t = threading.Thread(target=adapter.start, args=(emit,))
    t.start()
    deadline = time.time() + 5
    while time.time() < deadline and len(out) < 4:
        time.sleep(0.01)
    adapter.stop()
    t.join(timeout=5)

    assert store.dead_letters() == []
    assert all(e is not None for e in out)
    kinds = [(e["body"]["event_type"], e["body"]["payload"]) for e in out]
    assert (("cycle_complete", {"cycle_count": 101})) in kinds
    assert (("state_change", {"from_state": "idle", "to_state": "running"})) in kinds
    assert (("state_change", {"from_state": "running", "to_state": "fault"})) in kinds
    assert adapter.health().state == "ok"


def test_probe_from_mapping(tmp_path):
    (tmp_path / "map.yaml").write_text(MAPPING, encoding="utf-8")
    cls = load_adapter_class(ADAPTER_DIR)
    info = cls().probe({"mapping_file": str(tmp_path / "map.yaml")})
    assert info.machine_class == "overlock"
    assert info.capabilities == ["event"]
    assert info.data_source == "native"
