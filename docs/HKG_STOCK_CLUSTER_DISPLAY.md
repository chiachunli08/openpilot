# Kia EV6 stock-cluster extension research

This work keeps the comma/sunnypilot on-device UI separate from the Kia stock
instrument cluster. It adds a Visuals master permission, explicit per-feature
data and compatibility gates, and a passive audit tool. It does **not** transmit
the unverified `0x161` or `0x162` messages.

## Pinned implementation state

| Component | Revision checked | Result |
|---|---|---|
| `TonyBinheWu/sunnypilot` | `hkg-enhanced` base `4fbe8adcdbe0d59358656e61eeda27fac9ab0fb3` | Branch inspected and modified in place |
| `TonyBinheWu/opendbc` | submodule `fa4874935666a796fb4dcb0f4afa4056c105216f` | Actual Hyundai controller, DBC and safety source used by this branch |
| [commaai/opendbc PR #1269](https://github.com/commaai/opendbc/pull/1269) | merged as `ba82d74efab890db6bd2e58c50227c1bc7009e62` | `CCNC_0x161/0x162` common-DBC work originated from 2023-24 Palisade/Telluride HDA2 research, not an EV6 support claim |

The vehicle is fingerprinted as a candidate only when all of these are true:

- Hyundai/Kia brand;
- exact `CAR.KIA_EV6` platform;
- CAN-FD flag;
- `CANFD_LKA_STEER_MSG`, which this branch derives from the observed HDA2 LKA
  steering message.

Candidate status is not verified compatibility. The verified EV6 profile
registry is intentionally empty until the evidence below is collected.

## Feature matrix

| Stock-cluster display | Candidate CAN/field | Proposed source and condition | Current evidence | Current state |
|---|---|---|---|---|
| Existing HDA/LFA icons | `0x1E0` `HDA_ICON`, `LFA_ICON` | Existing controller state, 20 Hz only on its existing eligible path | Already packed and allowed by this branch | Existing behavior preserved; new master switch does not touch it |
| Left/right lane-change arrow | `0x161` `LCA_LEFT_ARROW`, `LCA_RIGHT_ARROW` | Fresh `modelV2.meta`; only `laneChangeStarting` or `laneChangeFinishing`, never direction signal alone or `preLaneChange` | DBC field only; EV6 destination bus/display unconfirmed | Semantic gate implemented; CAN output disabled |
| Lane lines and lane area | `0x161` `LANELINE_LEFT/RIGHT`, `LANE_HIGHLIGHT` | Fresh valid lane probabilities; white when detected, green only while lateral assist is active, orange only for a real side-specific warning | DBC color meanings and EV6 rendering unconfirmed | Semantic stale/invalid clearing implemented; CAN output disabled |
| Navigation icon | `0x161` `NAV_ICON` | Fresh valid `navInstruction`; this field is only a generic icon/color, not a turn arrow or route | DBC field only; EV6 rendering unconfirmed | Semantic stale/invalid clearing implemented; CAN output disabled |
| Generic target box | `0x162` lead slots | Fresh valid generic lead/track after range checks | Slot coordinates, signed lateral origin and EV6 rendering unconfirmed | Semantic filtering implemented; CAN output disabled |
| Vehicle shape | `0x162` lead enum | Requires a reliable vehicle class | `modelV2` and `radarState` expose generic leads, not a proven vehicle class for this use | Missing source data; disabled |
| Pedestrian shape | `0x162` lead enum | Requires a reliable pedestrian class | No current model/radar output supplies it | Missing source data; disabled |
| Bicycle shape | `0x162` lead enum | Requires a reliable bicycle class | No current model/radar output supplies it | Missing source data; disabled |
| Motorcycle shape | `0x162` lead enum | Requires a reliable motorcycle class | No current model/radar output supplies it | Missing source data; disabled |
| Traffic-cone shape | `0x162` lead enum | Requires a reliable cone class | No current model/radar output supplies it | Missing source data; disabled |

The DBC enum listing a shape proves only that a researched message has an enum;
it does not prove that this EV6 cluster accepts that value or that sunnypilot has
the classification data needed to select it.

## Visuals and sunnylink behavior

`HkgStockClusterDisplay` appears in Visuals only after an EV6 HDA2 CAN-FD
fingerprint. The same candidate capability is exported in the sunnylink settings
schema, so the permission can also be saved remotely.

This is a master **permission**, not an unsafe force switch. The activation rule
for every feature is:

```text
user permission
AND exact verified vehicle profile
AND that feature is verified for the profile
AND fresh valid source data
```

If any term is false, that added display intent is cleared. The current build
shows `0 verified`, because no EV6 profile has yet met the compatibility rule.
Turning the permission on therefore produces no new cluster CAN traffic.

## Why active transmission is still blocked

1. This branch currently sends `LFAHDA_CLUSTER` (`0x1E0`, 16 bytes) through the
   existing Hyundai CAN-FD path. On an HDA2/LKA-steering vehicle with stock
   longitudinal control, even that existing message is not emitted by the
   controller's current condition.
2. There is no `CCNC_0x161` or `CCNC_0x162` sender in this branch.
3. The Hyundai CAN-FD Panda safety TX lists contain `0x1E0`, but not `0x161` or
   `0x162`. A Python sender alone would therefore not establish a valid path.
4. DBC presence, a received frame, a successful send, an ACK, or Panda acceptance
   cannot individually establish instrument-cluster compatibility.

No Panda rule, forwarding rule, ECU communication state, steering field,
longitudinal field, or existing HDA/LFA/LKA behavior was changed by this work.

## Passive data required from the EV6

Collect these without transmitting test messages or disabling an ECU:

- all **received** Panda buses (`src` 0 through 127), preserving source bus and
  monotonic timestamp;
- CAN IDs `0x161`, `0x162`, and `0x1E0`, including frames with unexpected lengths;
- the exact `CarParamsPersistent`/fingerprint and `carFw`, especially the CAN-FD
  combination meter queried at diagnostic address `0x7C6`;
- model year, market, instrument-cluster software version, head-unit software
  version, and whether the head unit is confirmed ccNC rather than inferred;
- synchronized instrument-cluster video and manual event labels.

Record separate, repeatable scenarios:

1. ignition on with all assistance idle;
2. HDA/LFA standby, active, override and disengaged;
3. left and right direction signal only;
4. left/right lane-change preparation, start, finish and cancellation;
5. visible left/right lane markings, deliberate factory lane warning, and loss of
   lane detection;
6. navigation with no route, active route, approaching a maneuver, rerouting and
   destination cancellation;
7. any situation where the stock cluster naturally displays a surrounding target.

Use the passive audit tool after exporting the raw frames to JSONL:

```bash
python tools/hkg_cluster/ev6_cluster_capture.py passive_frames.jsonl audited.jsonl
```

It verifies payload length, HKG CAN-FD CRC, counter continuity, timestamp order,
observed rate, and changed bytes per event label. It always reports compatibility
as unconfirmed because those transport checks do not prove screen behavior.

## Criteria for a later active implementation

An exact profile may be added only after passive data and synchronized video
establish the original sender, receiving bus, 32-byte format, frequency,
counter/checksum behavior, unchanged template bytes, and reproducible field-to-
screen correlations. Each feature must be confirmed independently.

Only then should a later change add, together:

- a copy-and-modify packer based on fresh stock frames, never a zero-filled whole message;
- per-feature freshness and clear-on-loss behavior;
- collision/forwarding handling for the factory frame;
- a minimal Panda allowlist entry for exact IDs, bus and length;
- replay tests proving existing control fields and `0x1E0` behavior are unchanged;
- stationary/bench validation before any closed-course vehicle test.

Unknown enum values must never be scanned on the vehicle. A failure in one
feature disables that feature only and cannot stop existing required messages.
