# EV6 stock-cluster passive audit tool

This tool audits **received** CAN frames for `0x161`, `0x162`, and the existing
`0x1E0` cluster message. It never opens a CAN socket and cannot transmit.

```bash
python tools/hkg_cluster/ev6_cluster_capture.py passive_frames.jsonl audited.jsonl
```

Input aliases are `timestamp_nanos`/`logMonoTime`, `source_bus`/`bus`/`src`,
`address`/`can_id`/`id`, and `data`/`dat`/`payload`. Add an `event` or `scenario`
label while recording, for example `stock_hda_active`, `left_lane_change_start`,
or `navigation_no_route`. The output retains every candidate raw frame and adds:

- expected versus observed payload length;
- received and computed HKG CAN-FD CRC;
- counter continuity;
- timestamp order and median observed rate;
- changed byte indices grouped by manually labelled event.

Bus values `128` and above are treated as transmit echo and excluded from
received-bus evidence. A final `summary` remains `unconfirmed` by design:
observing an ID, a correct CRC, an ACK, or a counter sequence is not proof that
an EV6 cluster supports active overrides. See
[`docs/HKG_STOCK_CLUSTER_DISPLAY.md`](../../docs/HKG_STOCK_CLUSTER_DISPLAY.md)
for the evidence and unlock criteria.
