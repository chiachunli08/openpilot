# YOLO Traffic Signal Visuals (experimental)

Branch: `hkg-yolo-traffic-signal-visuals`

This feature is display-only. It does not feed YOLO detections into planning, longitudinal control, steering, braking, desire, or Panda safety.

## Source model

- Upstream project: `UsamaMasood12/YOLO11s-Traffic-Signal-Detection`
- Artifact: `runs/detect/yolo11s_custom_dataset/weights/best.onnx`
- Size: 37,936,019 bytes
- Git blob SHA-1: `acf5b39c8e83184587410f484dcb2213fee3bb4e`
- Input: 640 x 640 RGB
- Classes: `green`, `left-green`, `left-red`, `left-yellow`, `red`, `yellow`
- The upstream README identifies the dataset as CC BY 4.0. The upstream repository does not currently provide a clear repository-wide license statement for all code/weights, so this branch downloads the artifact from its original repository instead of redistributing the weight file.

## Runtime architecture

Chestnut remains single-owner: the existing `modeld_v2` process owns USB/AMD. No second process opens Chestnut.

For each admitted YOLO pass:

1. The primary driving model runs first.
2. Admission control checks the previous driving-model frame-drop percentage and the measured primary model time.
3. A road-camera NV12 frame is sampled directly to a 640 x 640 RGB model canvas using NumPy. OpenCV is not required.
4. YOLO11s runs explicitly on the same Chestnut `AMD` device.
5. Only the highest-relevance signal class/confidence is written to `/dev/shm/sunnypilot_traffic_signal_yolo.json`.
6. The HUD reads that display-only state and renders a traffic-light card below the Experimental Mode button.

## Primary-model protection

- Feature is off by default.
- The Visuals toggle is shown only for a Chestnut-backed tinygrad model runner.
- Download, ONNX loading, JIT warmup and first full-path validation require the vehicle to be in Park, stationary, and controls inactive.
- Before moving inference is permitted, a full real-camera-frame auxiliary pass must validate while parked.
- Maximum normal rate: 2 Hz.
- Primary model must be <= 22 ms on the previous measured pass.
- Previous model frame drop must be <= 0.5%.
- YOLO GPU inference target: <= 12 ms.
- Entire auxiliary path target: <= 18 ms.
- Moderate overrun backs off and drops to 1 Hz.
- Auxiliary path > 25 ms disables further YOLO inference until modeld restarts and parked validation succeeds again.

These limits are intentionally conservative and must be validated on the actual C3X + Chestnut combination before merging into `hkg-enhanced`.

## Test procedure

1. Install/switch to branch `hkg-yolo-traffic-signal-visuals` while parked.
2. Connect Chestnut and confirm the normal driving model loads successfully.
3. Start the car but remain in **P**. Open Settings -> Visuals -> `YOLO Traffic Signal Detection (Experimental)` / `YOLO 交通號誌辨識（實驗）` and enable it.
4. Keep the vehicle in **P** and controls disengaged while the model downloads, loads, warms up, and runs the real-camera full-path timing validation. Do not shift out of Park during this stage.
5. Confirm normal model operation first. Do not begin moving if `Driving Model Lagging`, Chestnut errors, or abnormal UI behavior appears during validation.
6. On a closed/controlled test route, verify red/yellow/green and left-arrow signal indications. The card appears below the Experimental Mode button.
7. Compare `Driving Model Lagging`, frame-drop percentage, main model timing, Chestnut temperature and GPU utilization with the feature OFF vs ON.
8. If frame drops increase, disable the feature and retain logs/state for tuning.

## Important limitation

The detector can misclassify signals, identify a signal that applies to another lane, or miss a signal. It is a visual aid only. It must not be used as a stop/go authority.
