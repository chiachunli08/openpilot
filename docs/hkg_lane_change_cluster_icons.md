# Kia EV6 stock-cluster lane-change-assist icons

Implementation baseline: sunnypilot `1f8a1540aa633c5a2f51a76df6d764c113d351ef`,
TonyBinheWu/opendbc `03f4ba63901497df0fe4d6aa01cfd3504fe7aa69`, and
sunnyhaibin/panda `74a0adced421e8b7acd728d0f9988ce225423f13`.

## Scope and present status

This feature computes display state only. It does not alter steering, acceleration,
braking, turn signals, or lane-change decisions. There is currently no verified EV6
profile in `VERIFIED_PROFILES`, so normal driving output of `0x161` remains disabled.
The existing parked one-shot test is separate and is not reused for driving output.

| Display | CAN | Field | Source | Semantic trigger | Status |
|---|---:|---|---|---|---|
| Left LCA icon | `0x161`, 32-byte CAN FD | `LCA_LEFT_ICON` | `carControl.latActive` + fresh `modelV2.meta` | hidden / gray standby / green explicit-ready or executing-left | State implemented; EV6 CAN output unverified and disabled |
| Right LCA icon | `0x161`, 32-byte CAN FD | `LCA_RIGHT_ICON` | `carControl.latActive` + fresh `modelV2.meta` | hidden / gray standby / green explicit-ready or executing-right | State implemented; EV6 CAN output unverified and disabled |
| Left/right road arrows | `0x161`, 32-byte CAN FD | `LCA_LEFT_ARROW`, `LCA_RIGHT_ARROW` | actual starting/finishing state | separate feature; not enabled by this switch | Unchanged |
| Wheel/LFA/HDA | `0x1E0`, 16-byte CAN FD | `LFA_ICON`, `HDA_ICON` | existing Hyundai controller | existing control state | Unchanged |

The public DBC maps LCA icon values as 0 hidden, 1 gray, 2 green, and 4 white.
The state machine does not use value 3 or invent a flashing schedule. READY and ACTIVE
both map to steady green until a synchronized CAN/video capture proves a distinct
factory behavior.

## Shared model path

Both stock `selfdrive/modeld/modeld.py` and
`sunnypilot/modeld_v2/modeld.py` publish the same cereal contract:

- `modelV2.meta.laneChangeState`
- `modelV2.meta.laneChangeDirection`

`lane_change_inputs_from_model()` normalizes that contract. The internal
`AutoLaneChangeController.auto_lane_change_allowed` readiness value is not currently
published by either path. Consequently PREPARING stays gray unless a future, explicit
and validated readiness source is supplied; a turn signal alone never produces green.

| Input state | Left icon | Right icon |
|---|---|---|
| master/switch off, lateral inactive, invalid or stale model | hidden | hidden |
| lateral active, lane change off or preparing with readiness unknown/blocked | gray | gray |
| explicit ready-left / ready-right | green / gray | gray / green |
| starting or finishing left / right | green / gray | gray / green |
| complete, cancel, pause, control exit | recomputed immediately; gray if still laterally active, otherwise hidden | same |

## Why normal CAN transmission is still disabled

`CCNC_0x161` also carries AEB/FCA, blind-spot, lane, alert, sound, set-speed,
HDA/LFA, driver-attention, background, CRC16 and counter fields. Packing only the two
LCA fields would zero unrelated fields. A DBC definition, an ACK, or the ability to
transmit is not proof that the EV6 cluster accepts this message.

The current Panda allowlist accepts `0x161` only with the separate
`CANFD_HKG_CLUSTER_TEST` safety flag, while Park, standstill, accelerator-off and all
controls-off interlocks are true. Its payload validator allows only the restricted
parked test values. No driving allowlist was added.

Before adding an EV6 verified profile and normal sender, collect:

1. Exact EV6 model year, cluster/head-unit part and firmware identifiers; confirm ccNC
   rather than inferring it from HDA2.
2. Passive logs on every harness-visible bus, preserving source bus, monotonic timestamp,
   CAN ID, payload length and data. Specifically check `0x161`, `0x1E0`, forwarding and
   transmitted-frame echo buses.
3. A synchronized cluster video and CAN capture for: LFA off/on/paused; left/right
   pre-change; blind-spot blocked; start; finish; cancel; and control exit.
4. The observed `0x161` source ECU, bus, exact period, counter sequence, CRC behavior,
   full neutral payload and every field that changes in each scene.
5. Evidence that taking ownership of `0x161` does not race an original ECU or suppress
   unrelated warnings. A verified complete-frame template is mandatory.

Only after those checks should a minimal, separate driving safety flag be considered.
It must authorize exactly ID `0x161`, its verified bus and 32-byte length, validate CRC,
counter and an allowlisted set of LCA field values, and reject modifications to all
other fields. The parked test flag must not be reused.

## Settings

On device: **Settings → Visuals → 換道輔助圖示跟隨 LFA**.
The switch is visible only for a fingerprinted EV6 HDA2 CAN-FD candidate and is disabled
with status `unavailable unverified vehicle profile` until an exact verified profile is
present. The same setting is exposed in the branch's sunnylink Visuals schema, but the
device remains the final compatibility gate.
