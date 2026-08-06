"""generic-modbus protocol layer - pure frame building/parsing, no I/O.

Implements the read-only subset OMP needs: function 0x03 (read holding
registers) and 0x04 (read input registers), over Modbus TCP (MBAP) and RTU
(CRC-16). Nothing here can write to a device - there is deliberately no
building of write function codes (constitutional read-only edge).
"""
from __future__ import annotations

import struct

READ_HOLDING = 0x03
READ_INPUT = 0x04


class ModbusError(ValueError):
    pass


# ---------------------------------------------------------------- addressing
def resolve_address(address: int) -> tuple[int, int]:
    """Map conventional register numbers to (function, offset).

    4xxxx/4xxxxx -> holding (0x03), 3xxxx/3xxxxx -> input (0x04).
    Plain offsets (< 10000) are treated as holding register offsets.
    """
    for base, func in ((400001, READ_HOLDING), (40001, READ_HOLDING),
                       (300001, READ_INPUT), (30001, READ_INPUT)):
        if base <= address < base + 9999:
            return func, address - base
    if 0 <= address < 10000:
        return READ_HOLDING, address
    raise ModbusError(f"unsupported register address {address}")


# ---------------------------------------------------------------- TCP framing
def build_read_tcp(tid: int, unit_id: int, func: int, offset: int,
                   count: int) -> bytes:
    pdu = struct.pack(">BHH", func, offset, count)
    return struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit_id) + pdu


def parse_read_tcp(frame: bytes, expect_tid: int, expect_func: int) -> list[int]:
    if len(frame) < 9:
        raise ModbusError("short TCP frame")
    tid, proto, length, unit = struct.unpack(">HHHB", frame[:7])
    if tid != expect_tid:
        raise ModbusError(f"transaction id mismatch {tid} != {expect_tid}")
    if proto != 0:
        raise ModbusError("bad protocol id")
    return _parse_pdu(frame[7:7 + length - 1], expect_func)


# ---------------------------------------------------------------- RTU framing
def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build_read_rtu(unit_id: int, func: int, offset: int, count: int) -> bytes:
    body = struct.pack(">BBHH", unit_id, func, offset, count)
    return body + struct.pack("<H", crc16(body))


def parse_read_rtu(frame: bytes, expect_unit: int, expect_func: int) -> list[int]:
    if len(frame) < 5:
        raise ModbusError("short RTU frame")
    body, crc = frame[:-2], struct.unpack("<H", frame[-2:])[0]
    if crc16(body) != crc:
        raise ModbusError("CRC mismatch")
    if body[0] != expect_unit:
        raise ModbusError(f"unit id mismatch {body[0]} != {expect_unit}")
    return _parse_pdu(body[1:], expect_func)


# ---------------------------------------------------------------- shared PDU
def _parse_pdu(pdu: bytes, expect_func: int) -> list[int]:
    func = pdu[0]
    if func == expect_func | 0x80:
        raise ModbusError(f"device exception code {pdu[1]}")
    if func != expect_func:
        raise ModbusError(f"function mismatch {func} != {expect_func}")
    byte_count = pdu[1]
    data = pdu[2:2 + byte_count]
    if len(data) != byte_count or byte_count % 2:
        raise ModbusError("byte count mismatch")
    return [struct.unpack(">H", data[i:i + 2])[0] for i in range(0, byte_count, 2)]


# ---------------------------------------------------------------- values
def decode_value(regs: list[int], reg_type: str, scale: float = 1):
    if reg_type == "u16":
        raw = regs[0]
    elif reg_type == "s16":
        raw = struct.unpack(">h", struct.pack(">H", regs[0]))[0]
    elif reg_type == "u32":
        raw = (regs[0] << 16) | regs[1]
    elif reg_type == "u32_swapped":
        raw = (regs[1] << 16) | regs[0]
    else:
        raise ModbusError(f"unsupported register type {reg_type!r}")
    value = raw * scale
    return int(value) if float(value) == int(value) else value


def reg_count(reg_type: str) -> int:
    return 2 if reg_type.startswith("u32") else 1
