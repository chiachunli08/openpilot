# Kia EV6 stock-cluster extension research

This work keeps the comma/sunnypilot on-device UI separate from the Kia stock
instrument cluster. It adds a Visuals master permission, explicit per-feature
data and compatibility gates, a passive audit tool, and an optional **parked,
one-shot active research test** for `0x161` and `0x162`. Normal driving does not
use these unverified messages.

## Pinned implementation state

| Component | Revision checked | Result |
|---|---|---|
| `TonyBinheWu/sunnypilot` | `hkg-enhanced` implementation base `ef0f8fd2697d8efb9e76474da7653a30c8b993ec` | Branch inspected and modified in place |
| `TonyBinheWu/opendbc` | `hkg-cluster-display-test` `741c1839fbca6d270bc10a388640e96d2e96feb3` (base `fa4874935666a796fb4dcb0f4afa4056c105216f`) | Actual Hyundai controller, DBC and safety source used by this branch |
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
| Left/right lane-change arrow | `0x161` `LCA_LEFT_ARROW`, `LCA_RIGHT_ARROW` | Later dynamic source: real executing lane-change state, never direction signal alone | DBC field only; EV6 rendering unconfirmed | Left and right synthetic test pages implemented; dynamic output disabled |
| Lane lines and lane area | `0x161` `LANELINE_LEFT/RIGHT`, `LANE_HIGHLIGHT` | Later dynamic source: fresh lane probabilities, assist state and real warnings | DBC color meanings and EV6 rendering unconfirmed | White, green and orange synthetic test pages implemented; dynamic output disabled |
| Navigation icon | `0x161` `NAV_ICON` | Later dynamic source: fresh navigation state; it is only a generic icon/color | DBC field only; EV6 rendering unconfirmed | Gray, green and white synthetic test pages implemented; dynamic output disabled |
| Generic target box | `0x162` lead slots | Later dynamic source: fresh generic lead/track after range checks | Slot coordinates, lateral origin and EV6 rendering unconfirmed | Synthetic box page implemented; dynamic output disabled |
| Vehicle shape | `0x162` lead enum | Reliable vehicle class required for later dynamic use | Current model/radar data is not a proven class source | Synthetic white-car page implemented; dynamic output disabled |
| Pedestrian shape | `0x162` lead enum | Reliable pedestrian class required for later dynamic use | No current model/radar output supplies it | Synthetic white-person page implemented; dynamic output disabled |
| Bicycle shape | `0x162` lead enum | Reliable bicycle class required for later dynamic use | No current model/radar output supplies it | Synthetic white-bicycle page implemented; dynamic output disabled |
| Motorcycle shape | `0x162` lead enum | Reliable motorcycle class required for later dynamic use | No current model/radar output supplies it | Synthetic white-motorcycle page implemented; dynamic output disabled |
| Traffic-cone shape | `0x162` lead enum | Reliable cone class required for later dynamic use | No current model/radar output supplies it | Synthetic orange-cone page implemented; dynamic output disabled |

The DBC enum listing a shape proves only that a researched message has an enum;
it does not prove that this EV6 cluster accepts that value or that sunnypilot has
the classification data needed to select it.

## Visuals and sunnylink behavior

`HkgStockClusterDisplay` appears in Visuals only after an EV6 HDA2 CAN-FD
fingerprint. The same candidate capability is exported in the sunnylink settings
schema, so the master permission can also be saved remotely.

`HkgStockClusterDisplayTest` appears immediately below it on the device. It is
deliberately **not** in the sunnylink schema: remote access cannot arm active CAN
research. Both switches must be on during startup, so turning the test on shows
`armed restart required` until the software/device is restarted.

This is a master **permission**, not an unsafe force switch. The activation rule
for every feature is:

```text
user permission
AND exact verified vehicle profile
AND that feature is verified for the profile
AND fresh valid source data
```

If any term is false, normal dynamic display intent is cleared. The current build
shows `0 verified`, because no EV6 profile has yet met the compatibility rule.
The one-shot test is a separate evidence-collection path and cannot authorize
normal driving output.

## Guarded active-test behavior

The test sends a restricted `CCNC_0x161`/`CCNC_0x162` pair on HDA2 E-CAN (logical
bus 1) at 20 Hz. The DBC packer generates the 32-byte payload, rolling counter and
HKG CAN-FD CRC. There is a two-second passive observation window before the first
transmit. Any received `0x161` or `0x162`, including an unexpected payload
length, on a real source bus aborts the test instead of competing with a factory
sender.

The 12 three-second pages are: clear; left arrow; right arrow; white lane view;
green lane view; orange lane view; gray navigation; green navigation; white
navigation; car/person/bicycle/cone; motorcycle/truck/generic boxes; clear.

Application and Panda safety independently require all of the following:

- exact Kia EV6 fingerprint with CAN-FD, HDA2 LKA steering and EV flags;
- both local settings armed at process initialization;
- valid CAN state, selector in P, standstill and `vEgoRaw` at most 0.1 m/s;
- accelerator not pressed and lateral/longitudinal control disengaged;
- no received factory `0x161`/`0x162` conflict;
- valid 32-byte length and HKG checksum;
- payload limited to the reviewed arrow, lane, assist-icon and four front/side
  object slots;
- a hard Panda budget of 1,600 accepted frames, above one normal 1,440-frame run
  but finite if the application runs away.

Panda rejects collision/AEB/BCA, warnings, sounds, set speed, speed limits,
vibration, fault, rear-object and unknown/reserved fields. It also rejects these
IDs on every other bus and in every safety mode where the explicit test flag is
absent. The one-shot setting clears on completion, timeout, message conflict or
vehicle-interlock failure. No ECU is disabled, and existing steering,
longitudinal, `0x1E0`, forwarding and normal HDA/LFA/LKA logic is changed.

### Vehicle test procedure

1. Park in a safe open location, keep the selector in P, and do not engage
   sunnypilot or cruise control.
2. In **Settings → Visuals**, enable the stock-cluster master permission, then
   enable **Send All EV6 Cluster Test Pages (Park Only)**.
3. Restart sunnypilot/the device while remaining in P. Start a continuous video
   showing the complete factory cluster before the restart finishes.
4. Do not press the accelerator, shift, or move for about 40 seconds. The test
   observes for two seconds and then advances automatically every three seconds.
5. Read the right-side status in Visuals afterward. `complete` means only that
   the planned frames passed local safety; it does not prove the cluster rendered
   them. Any `aborted ...` status identifies the interlock that stopped the test.

If any unexpected warning, chime or vehicle behavior appears, stop the vehicle
test and power down safely. This test must not be used while driving.

## Passive data required from the EV6

Collect these passively before or alongside the parked test; no ECU is disabled:

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

## Criteria for later normal dynamic display

An exact profile may be added only after passive data and synchronized video
establish the original sender, receiving bus, 32-byte format, frequency,
counter/checksum behavior, unchanged template bytes, and reproducible field-to-
screen correlations. Each feature must be confirmed independently.

Only then should a later change add normal state-driven output, together:

- a copy-and-modify packer based on fresh stock frames, never a zero-filled whole message;
- per-feature freshness and clear-on-loss behavior;
- collision/forwarding handling for the factory frame;
- a minimal Panda rule for exact IDs, bus, length and verified production fields;
- replay tests proving existing control fields and `0x1E0` behavior are unchanged;
- stationary/bench validation before any closed-course vehicle test.

Unknown enum values must never be scanned on the vehicle. A failure in one
feature disables that feature only and cannot stop existing required messages.
