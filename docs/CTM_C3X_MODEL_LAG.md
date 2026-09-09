# CTM on comma 3X versus comma four

Investigation base: `TonyBinheWu/sunnypilot` `hkg-enhanced`, commit
`2e9e150a16bb7b137207fde36907652c643119d3`; tinygrad
`e837e367aac9e1a66e689f4f32ce20ca9367df13`. No device log was supplied, so the
reported c3x lag is not yet attributed to a measured cause.

## Confirmed source findings

- The [sunnypilot CTM announcement](https://community.sunnypilot.ai/t/cinque-terre-model-september-04-2026/7046)
  lists comma four or comma 3X plus Chestnut. It is not a model intended to run on
  the phone-class processor alone.
- The [pinned Chestnut catalog](https://github.com/sunnypilot/sunnypilot-models/blob/fdfa1c7357c9605db701f391cc392a66b926a03d/docs/driving_models_chestnut_v25.json)
  identifies CTM as reference `68b5f8e48602f4f88041efd7de6c99e97fda454e`,
  tinygrad runner, generation 12, 20 Hz. CTMV2 is a separate bundle with reference
  `37bfa1413edcdc2e8844984b83727c33f81d8f46`; record which is selected. The catalog
  tinygrad revision matches this branch. This is not proof of on-device artifact identity.
- `process_config.py` selects `modeld_tinygrad` for a selected tinygrad bundle.
  Both stock and selected-model runners count jumps in consumed camera frame IDs.
  `frameDropPerc` is a filtered dropped-frame percentage, not display FPS.
- `selfdrived.py` triggers `modeldLagging` at `frameDropPerc > 1`. The nearby
  events comment still says 20%; the executable condition is 1%. This diagnostic
  change does not alter either the threshold or disengagement behavior.
- Both runners have a 20 Hz / 50 ms processing period. `modelExecutionTime`
  measures `model.run()`, including copies, output readback/parsing and scheduled
  Chestnut telemetry. It is not a GPU-only inference timer and excludes some
  surrounding receive/publish work. A low median alone cannot exclude lag.

## Different camera input costs

At the investigation base above, `modeld/SConscript` selected OS geometry for
mici (c4), AR/OX otherwise on comma hardware. The subsequent
[compiler alignment](MODEL_COMPILATION_ALIGNMENT.md) builds both geometries;
runtime still selects the detected sensor's dimensions. `nv12_info.py` and
`compile_modeld.py:nv12_copy_size` yield for these configurations:

| Device | Camera frame | Padded bytes per camera copied by the packed-input path | Two cameras at 20 Hz |
|---|---|---:|---:|
| comma 3X | 1928 × 1208 | 3,735,552 | 149.42 MB/s |
| comma four | 1344 × 760 | 1,622,016 | 64.88 MB/s |

These are calculated input volumes (decimal MB), not measured USB throughput or
neural-network input sizes. The packed-input path copies these frames before
warping. The actual downloaded pickle path must be checked in modeld startup
logs. c3x has about 2.30 times the image payload on this path. Copy/USB/warp cost,
thermal throttling, camera synchronization and telemetry latency are candidates
to measure, not established diagnoses. Do not resize frames or change trained
model timing based only on this comparison.

## Read-only capture

On each device, with the same CTM version selected and its normal processes
running, capture the period in which the alert occurs. Start the command while
parked; a driver must not operate SSH while driving. No extra model is loaded.

```bash
cd /data/openpilot
python tools/scripts/diagnose_model_lag.py --seconds 60 --output /data/ctm_c3x.jsonl
```

Use a different output name for c4, and a new filename for each run. Existing
files are not overwritten. To inspect a saved rlog instead:

```bash
python tools/scripts/diagnose_model_lag.py --rlog /path/to/rlog.zst --output /data/ctm_rlog.jsonl
```

The JSONL records exact code/model selection for live capture; per-message model
time and reported drop percentage; camera timestamps; device utilization and
temperature; and Chestnut voltage, faults, PCIe state, clocks, temperatures and
USB link speed/error counters. It omits network credentials, GPS and USB serials.
Unavailable data is represented as unknown, not fabricated zeros. The rlog mode
does not attribute the analyzing computer's code/model selection to the vehicle.

The summary reports median/p95/max execution time, samples exceeding 50 ms,
reported drop percentage, actual big-model flags and observed service rates.
Live SubMaster collection can miss messages under load; its observed gaps must
not be relabeled as model frame drops. Invalid/dead model samples do not enter
timing distributions. A capture with no valid model samples proves nothing
about model performance. Raw timestamps remain available for correlation.

## How to use the evidence

1. Check the model bundle reference and `valid_big_model_samples`. Selecting CTM
   does not prove it stayed active; the runner can fall back to the small model.
2. Compare camera publication intervals with model timing and `frameDropPerc`.
   Regular cameras plus slow model cycles point downstream of capture. Camera
   gaps/synchronization faults require checking camerad and its logs as well.
3. Correlate bad intervals with Chestnut/device temperature, clocks, power/PCIe
   events and USB speed/error counters. Nominal negotiated USB speed alone does
   not establish achieved bandwidth or cable reliability.
4. Provide both captures and the modeld startup/error log around the incident.
   If practical, repeat on c3x with the same optional navigation/UI/radar settings
   disabled one at a time to isolate host load. Absence of an alert after a single
   run is not proof of a fix.

The diagnostic tool does not suppress alerts, reduce the model rate, replace
models, change camera capture sizes or send CAN. See
[MODEL_COMPILATION_ALIGNMENT.md](MODEL_COMPILATION_ALIGNMENT.md) for the later
compile-only optimization; already downloaded CTM files are not rebuilt by it.
