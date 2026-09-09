#!/usr/bin/env python3
"""Audit passive EV6 cluster CAN captures without transmitting any CAN."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import TextIO

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from opendbc.car.hyundai.hyundaicanfd import hkg_can_fd_checksum
from openpilot.sunnypilot.selfdrive.car.hkg_cluster_display import (
  DBC_RESEARCH_SOURCE,
  EXPECTED_PAYLOAD_BYTES,
)


def _first(row: dict, names: tuple[str, ...]):
  for name in names:
    if name in row:
      return row[name]
  raise KeyError(f"missing one of: {', '.join(names)}")


def _parse_int(value) -> int:
  return value if isinstance(value, int) else int(str(value), 0)


def _parse_timestamp_nanos(row: dict) -> int:
  for key in ("timestamp_nanos", "timestampNanos", "logMonoTime", "mono_time_nanos"):
    if key in row:
      return _parse_int(row[key])
  if "timestamp_sec" in row:
    return round(float(row["timestamp_sec"]) * 1e9)
  raise KeyError("missing nanosecond timestamp or timestamp_sec")


def _parse_data(value) -> bytes:
  if isinstance(value, list):
    return bytes(value)
  if not isinstance(value, str):
    raise TypeError("payload must be a hexadecimal string or byte list")
  value = value.strip().lower().removeprefix("0x")
  for separator in (" ", ":", "-", "_"):
    value = value.replace(separator, "")
  return bytes.fromhex(value)


def _write(output: TextIO, record: dict) -> None:
  output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _stream_stats() -> dict:
  return {
    "frames": 0,
    "received_frames": 0,
    "valid_lengths": 0,
    "invalid_lengths": 0,
    "valid_checksums": 0,
    "invalid_checksums": 0,
    "counter_gaps": 0,
    "out_of_order_timestamps": 0,
    "timestamps": [],
    "intervals_s": [],
    "last_timestamp": None,
    "last_counter": None,
    "last_data": None,
    "changed_bytes": set(),
    "events": defaultdict(lambda: {"frames": 0, "changed_bytes": set()}),
  }


def _summarize_stream(bus: int, address: int, stats: dict) -> dict:
  intervals = stats["intervals_s"]
  median_period = statistics.median(intervals) if intervals else None
  return {
    "source_bus": bus,
    "address": f"0x{address:03X}",
    "expected_payload_length": EXPECTED_PAYLOAD_BYTES[address],
    "frames": stats["frames"],
    "received_frames": stats["received_frames"],
    "valid_lengths": stats["valid_lengths"],
    "invalid_lengths": stats["invalid_lengths"],
    "valid_checksums": stats["valid_checksums"],
    "invalid_checksums": stats["invalid_checksums"],
    "counter_gaps": stats["counter_gaps"],
    "out_of_order_timestamps": stats["out_of_order_timestamps"],
    "median_period_s": median_period,
    "median_frequency_hz": (1.0 / median_period) if median_period and median_period > 0.0 else None,
    "changed_byte_indices": sorted(stats["changed_bytes"]),
    "events": {
      event: {"frames": values["frames"], "changed_byte_indices": sorted(values["changed_bytes"])}
      for event, values in sorted(stats["events"].items())
    },
  }


def convert_stream(input_file: TextIO, output_file: TextIO) -> None:
  streams: dict[tuple[int, int], dict] = defaultdict(_stream_stats)
  input_lines = candidate_lines = parse_errors = 0

  for line_number, line in enumerate(input_file, 1):
    if not line.strip():
      continue
    input_lines += 1
    try:
      source = json.loads(line)
      timestamp_nanos = _parse_timestamp_nanos(source)
      source_bus = _parse_int(_first(source, ("source_bus", "bus", "src")))
      address = _parse_int(_first(source, ("address", "can_id", "id")))
      data = _parse_data(_first(source, ("data", "dat", "payload")))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
      parse_errors += 1
      _write(output_file, {
        "record_type": "input_error",
        "input_line": line_number,
        "error": str(error),
        "raw_input": line.rstrip("\n"),
      })
      continue

    if address not in EXPECTED_PAYLOAD_BYTES:
      continue
    candidate_lines += 1
    event = str(source.get("event", source.get("scenario", "unlabelled")))
    received_bus = 0 <= source_bus < 128
    expected_length = EXPECTED_PAYLOAD_BYTES[address]
    accepted_length = len(data) == expected_length
    stats = streams[(source_bus, address)]
    stats["frames"] += 1
    stats["events"][event]["frames"] += 1

    timestamp_accepted = timestamp_nanos > 0
    counter = data[2] if accepted_length else None
    received_checksum = int.from_bytes(data[:2], "little") if accepted_length else None
    computed_checksum = hkg_can_fd_checksum(address, None, bytearray(data)) if accepted_length else None
    checksum_valid = received_checksum == computed_checksum if accepted_length else None
    counter_delta = None
    changed_byte_indices: list[int] = []

    if received_bus:
      stats["received_frames"] += 1
      if accepted_length:
        stats["valid_lengths"] += 1
      else:
        stats["invalid_lengths"] += 1

      prior_timestamp = stats["last_timestamp"]
      if prior_timestamp is not None:
        if timestamp_nanos <= prior_timestamp:
          timestamp_accepted = False
          stats["out_of_order_timestamps"] += 1
        else:
          stats["intervals_s"].append((timestamp_nanos - prior_timestamp) / 1e9)

      if accepted_length:
        if checksum_valid:
          stats["valid_checksums"] += 1
        else:
          stats["invalid_checksums"] += 1
        prior_counter = stats["last_counter"]
        if prior_counter is not None:
          counter_delta = (counter - prior_counter) % 256
          if counter_delta != 1:
            stats["counter_gaps"] += 1
        prior_data = stats["last_data"]
        if prior_data is not None:
          changed_byte_indices = [index for index, (before, after) in enumerate(zip(prior_data, data, strict=True)) if before != after]
          stats["changed_bytes"].update(changed_byte_indices)
          stats["events"][event]["changed_bytes"].update(changed_byte_indices)
        stats["last_counter"] = counter
        stats["last_data"] = data
      stats["last_timestamp"] = timestamp_nanos

    rejection = None
    if not received_bus:
      rejection = "transmit_echo_or_invalid_bus"
    elif not timestamp_accepted:
      rejection = "non_positive_or_out_of_order_timestamp"
    elif not accepted_length:
      rejection = f"wrong_payload_length:{len(data)}"

    _write(output_file, {
      "record_type": "passive_cluster_frame",
      "input_line": line_number,
      "timestamp_nanos": timestamp_nanos,
      "source_bus": source_bus,
      "address": f"0x{address:03X}",
      "payload_length": len(data),
      "expected_payload_length": expected_length,
      "data": data.hex(),
      "event": event,
      "received_bus": received_bus,
      "accepted_length": accepted_length,
      "timestamp_accepted": timestamp_accepted,
      "received_checksum": received_checksum,
      "computed_checksum": computed_checksum,
      "checksum_valid": checksum_valid,
      "counter": counter,
      "counter_delta": counter_delta,
      "changed_byte_indices": changed_byte_indices,
      "rejection": rejection,
      "compatibility_proof": False,
      "dbc_research_source": DBC_RESEARCH_SOURCE,
    })

  summaries = [_summarize_stream(bus, address, stats) for (bus, address), stats in sorted(streams.items())]
  _write(output_file, {
    "record_type": "summary",
    "input_lines": input_lines,
    "candidate_lines": candidate_lines,
    "parse_errors": parse_errors,
    "streams": summaries,
    "compatibility_state": "unconfirmed",
    "active_transmission_authorized": False,
    "note": "Observed IDs, ACKs, valid counters, and valid checksums do not by themselves prove EV6 cluster compatibility.",
    "dbc_research_source": DBC_RESEARCH_SOURCE,
  })


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("input", type=Path, help="JSONL containing passive raw CAN frames and optional event/scenario labels")
  parser.add_argument("output", nargs="?", type=Path, help="audited JSONL (stdout when omitted)")
  args = parser.parse_args()

  with args.input.open(encoding="utf-8") as input_file:
    if args.output is None:
      convert_stream(input_file, sys.stdout)
    else:
      with args.output.open("w", encoding="utf-8") as output_file:
        convert_stream(input_file, output_file)


if __name__ == "__main__":
  main()
