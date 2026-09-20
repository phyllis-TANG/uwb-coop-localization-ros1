#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Incrementally decode Nooploop NLink LinkTrack Node Frame3 packets."""

from __future__ import division


FRAME_HEADER = 0x55
FUNCTION_MARK = 0x05
FIXED_FRAME_LENGTH = 22
NODE_BLOCK_LENGTH = 7
MAX_FRAME_LENGTH = 2048


def read_serial_chunk(serial_port, max_bytes):
    """Wait for one byte, then drain only bytes already buffered.

    Reading the full requested size with a timeout groups 50 Hz frames into
    bursts and assigns them nearly identical ROS timestamps. A one-byte read
    preserves the timeout for reconnects while keeping frame latency low.
    """
    data = serial_port.read(1)
    if not data or max_bytes == 1:
        return data

    waiting = serial_port.inWaiting()
    if waiting > 0:
        data += serial_port.read(min(waiting, max_bytes - 1))
    return data


def decode_uint16_le(data, offset):
    return data[offset] | (data[offset + 1] << 8)


def decode_uint32_le(data, offset):
    return (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
        | (data[offset + 3] << 24)
    )


def decode_int24_le(data, offset):
    value = (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
    )
    if value & 0x800000:
        value -= 1 << 24
    return value


class NodeMeasurement(object):
    def __init__(
            self,
            role,
            node_id,
            distance_m,
            fp_rssi_db,
            rx_rssi_db):
        self.role = role
        self.node_id = node_id
        self.distance_m = distance_m
        self.fp_rssi_db = fp_rssi_db
        self.rx_rssi_db = rx_rssi_db


class Frame3(object):
    def __init__(
            self,
            role,
            node_id,
            local_time_ms,
            system_time_ms,
            voltage_v,
            measurements,
            raw):
        self.role = role
        self.node_id = node_id
        self.local_time_ms = local_time_ms
        self.system_time_ms = system_time_ms
        self.voltage_v = voltage_v
        self.measurements = measurements
        self.raw = raw


def decode_frame3(frame):
    """Decode one checksum-validated Frame3 packet."""
    data = bytearray(frame)

    if len(data) < FIXED_FRAME_LENGTH:
        raise ValueError("Frame3 packet is shorter than 22 bytes")
    if data[0] != FRAME_HEADER or data[1] != FUNCTION_MARK:
        raise ValueError("Frame3 header or function mark is invalid")

    declared_length = decode_uint16_le(data, 2)
    if declared_length != len(data):
        raise ValueError("Frame3 declared length does not match packet")

    node_count = data[20]
    expected_length = FIXED_FRAME_LENGTH + NODE_BLOCK_LENGTH * node_count
    if declared_length != expected_length:
        raise ValueError("Frame3 length does not match node count")

    if (sum(data[:-1]) & 0xff) != data[-1]:
        raise ValueError("Frame3 checksum is invalid")

    measurements = []
    offset = 21
    for unused_index in range(node_count):
        measurements.append(
            NodeMeasurement(
                role=data[offset],
                node_id=data[offset + 1],
                distance_m=decode_int24_le(data, offset + 2) / 1000.0,
                fp_rssi_db=data[offset + 5] / -2.0,
                rx_rssi_db=data[offset + 6] / -2.0,
            )
        )
        offset += NODE_BLOCK_LENGTH

    return Frame3(
        role=data[4],
        node_id=data[5],
        local_time_ms=decode_uint32_le(data, 6),
        system_time_ms=decode_uint32_le(data, 10),
        voltage_v=decode_uint16_le(data, 18) / 1000.0,
        measurements=measurements,
        raw=bytearray(data),
    )


class Frame3StreamParser(object):
    """Recover valid Frame3 packets from arbitrary serial byte chunks."""

    def __init__(self, max_frame_length=MAX_FRAME_LENGTH):
        self.buffer = bytearray()
        self.max_frame_length = max_frame_length
        self.discarded_bytes = 0
        self.bad_checksums = 0
        self.invalid_lengths = 0

    def feed(self, data):
        if data:
            self.buffer.extend(bytearray(data))

        frames = []
        while True:
            header_index = self._find_header()
            if header_index < 0:
                self._retain_possible_header_prefix()
                break

            if header_index:
                del self.buffer[:header_index]
                self.discarded_bytes += header_index

            if len(self.buffer) < 4:
                break

            frame_length = decode_uint16_le(self.buffer, 2)
            if (
                    frame_length < FIXED_FRAME_LENGTH
                    or frame_length > self.max_frame_length):
                del self.buffer[0]
                self.discarded_bytes += 1
                self.invalid_lengths += 1
                continue

            if len(self.buffer) < frame_length:
                break

            candidate = self.buffer[:frame_length]
            if (sum(candidate[:-1]) & 0xff) != candidate[-1]:
                del self.buffer[0]
                self.discarded_bytes += 1
                self.bad_checksums += 1
                continue

            try:
                frame = decode_frame3(candidate)
            except ValueError:
                del self.buffer[0]
                self.discarded_bytes += 1
                self.invalid_lengths += 1
                continue

            frames.append(frame)
            del self.buffer[:frame_length]

        return frames

    def _find_header(self):
        limit = len(self.buffer) - 1
        for index in range(max(0, limit)):
            if (
                    self.buffer[index] == FRAME_HEADER
                    and self.buffer[index + 1] == FUNCTION_MARK):
                return index
        return -1

    def _retain_possible_header_prefix(self):
        if self.buffer and self.buffer[-1] == FRAME_HEADER:
            discarded = len(self.buffer) - 1
            if discarded:
                del self.buffer[:-1]
                self.discarded_bytes += discarded
        else:
            self.discarded_bytes += len(self.buffer)
            del self.buffer[:]
