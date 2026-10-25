"""Small, read-only ROS1 v2 decoder for embedded message schemas.

Only uncompressed chunks are supported. No ROS installation or deserialization
of executable Python/pickle data is involved. Format failures raise BagError.
"""
import math
import re
import struct
from pathlib import Path

import numpy as np


class BagError(ValueError):
    """Malformed bag, schema, or message payload."""


def require(condition, message):
    if not condition:
        raise BagError(message)


def _take(blob, position, length, context):
    if length < 0 or position < 0 or position + length > len(blob):
        raise BagError("truncated {} at byte {} (need {})".format(context, position, length))
    return blob[position:position + length], position + length


def fields(blob):
    position, result = 0, {}
    while position < len(blob):
        raw, position = _take(blob, position, 4, "header field length")
        length = struct.unpack("<I", raw)[0]
        field, position = _take(blob, position, length, "header field")
        require(b"=" in field, "header field has no '=' separator")
        key, value = field.split(b"=", 1)
        key = key.decode("utf-8")
        require(key not in result, "duplicate header key: " + key)
        result[key] = value
    return result


def records(blob, start=0):
    position = start
    while position < len(blob):
        raw, position = _take(blob, position, 4, "record header length")
        length = struct.unpack("<I", raw)[0]
        header, position = _take(blob, position, length, "record header")
        raw, position = _take(blob, position, 4, "record data length")
        length = struct.unpack("<I", raw)[0]
        data, position = _take(blob, position, length, "record data")
        yield fields(header), data


def u32(value):
    require(len(value) == 4, "expected uint32 bag-header field")
    return struct.unpack("<I", value)[0]


def ns(value):
    require(len(value) == 8, "expected ROS time bag-header field")
    seconds, nanos = struct.unpack("<II", value)
    require(nanos < 10**9, "invalid ROS timestamp nanoseconds")
    return seconds * 10**9 + nanos


def load_bag(path):
    """Return (connections, [(connection_id, receipt_ns, message_bytes)])."""
    blob = Path(path).read_bytes()
    require(blob.startswith(b"#ROSBAG V2.0\n"), "not a ROS1 v2 bag")
    connections, messages = {}, []

    def handle(header, data, in_chunk=False):
        require("op" in header and len(header["op"]) == 1, "missing/invalid bag operation")
        operation = header["op"][0]
        if operation == 7:
            info = fields(data)
            item = {
                "topic": header["topic"].decode("utf-8"),
                "type": info["type"].decode("utf-8"),
                "definition": info["message_definition"].decode("utf-8"),
                "md5sum": info["md5sum"].decode("utf-8"),
                "callerid": info.get("callerid", b"").decode("utf-8"),
            }
            identity = u32(header["conn"])
            if identity in connections:
                require(connections[identity] == item, "conflicting repeated connection schema")
            connections[identity] = item
        elif operation == 2:
            messages.append((u32(header["conn"]), ns(header["time"]), data))
        elif operation == 5:
            require(not in_chunk, "nested bag chunks are unsupported")
            compression = header.get("compression", b"").decode("ascii", "replace")
            require(compression == "none", "unsupported ROS1 chunk compression: " + compression)
            require(u32(header["size"]) == len(data), "uncompressed chunk size mismatch")
            for child_header, child_data in records(data):
                handle(child_header, child_data, True)
        elif operation not in (3, 4, 6):
            raise BagError("unsupported bag operation: {}".format(operation))

    try:
        for header, data in records(blob, 13):
            handle(header, data)
        require(bool(messages), "bag contains no messages")
        require(all(identity in connections for identity, _, _ in messages),
                "message refers to an unknown connection")
    except KeyError as error:
        raise BagError("missing bag/header field: {}".format(error)) from error
    return connections, messages


PRIMITIVES = {
    "bool": "?", "byte": "b", "char": "B", "int8": "b", "uint8": "B",
    "int16": "h", "uint16": "H", "int32": "i", "uint32": "I",
    "int64": "q", "uint64": "Q", "float32": "f", "float64": "d",
}


class Decoder:
    def __init__(self, name, definition):
        self.definitions = {name: []}
        current = name
        for original in definition.splitlines():
            line = original.split("#", 1)[0].strip()
            if not line or line.startswith("==="):
                continue
            if line.startswith("MSG: "):
                current = line[5:].strip()
                self.definitions[current] = []
            elif "=" not in line:
                parts = line.split()
                require(len(parts) == 2, "unsupported ROS schema line: " + line)
                self.definitions[current].append(tuple(parts))

    def decode(self, data, kind):
        self.data, self.pos = data, 0
        value = self.value(kind, kind.split("/")[0])
        require(self.pos == len(data), "extra message bytes: {} of {} consumed for {}".format(
            self.pos, len(data), kind))
        return value

    def unpack(self, fmt):
        raw, self.pos = _take(self.data, self.pos, struct.calcsize("<" + fmt), "message field")
        values = struct.unpack("<" + fmt, raw)
        return values[0] if len(values) == 1 else values

    def value(self, kind, package):
        array = re.fullmatch(r"(.+)\[(\d*)\]", kind)
        if array:
            length = int(array[2]) if array[2] else self.unpack("I")
            # Every field type used in this dataset occupies at least one byte.
            require(length <= len(self.data) - self.pos,
                    "array length exceeds remaining message payload")
            return [self.value(array[1], package) for _ in range(length)]
        if kind in PRIMITIVES:
            return self.unpack(PRIMITIVES[kind])
        if kind == "string":
            length = self.unpack("I")
            raw, self.pos = _take(self.data, self.pos, length, "ROS string")
            return raw.decode("utf-8")
        if kind in ("time", "duration"):
            seconds, nanos = self.unpack("II" if kind == "time" else "ii")
            if kind == "time":
                require(nanos < 10**9, "invalid message timestamp nanoseconds")
            return {"secs": seconds, "nsecs": nanos}
        if kind == "Header":
            kind = "std_msgs/Header"
        elif "/" not in kind:
            kind = package + "/" + kind
        require(kind in self.definitions, "missing embedded ROS definition: " + kind)
        return {name: self.value(field_type, kind.split("/")[0])
                for field_type, name in self.definitions[kind]}


def stats(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return {"n": 0}
    return {"n": int(len(values)), "mean": float(values.mean()),
            "median": float(np.median(values)), "std": float(values.std()),
            "min": float(values.min()), "p05": float(np.quantile(values, .05)),
            "p95": float(np.quantile(values, .95)), "max": float(values.max())}


def stamp(message):
    value = message["header"]["stamp"]
    return value["secs"] * 10**9 + value["nsecs"]


def yaw(quaternion):
    q = quaternion
    return math.atan2(2 * (q["w"] * q["z"] + q["x"] * q["y"]),
                      1 - 2 * (q["y"]**2 + q["z"]**2))
