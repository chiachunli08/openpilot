# Sunnypilot Model Selector Port

## Goal

Add sunnypilot's current driving-model selection experience to CarrotPilot while preserving
Carrot-specific controls and its USB-eGPU behavior. The feature must support independent model
selection for the built-in QCOM accelerator and a connected USB eGPU.

## Approved scope

- Fetch and cache the current sunnypilot QCOM and USB-eGPU model catalogs.
- Select, download, cancel, verify, retain, and clear cached model bundles while offroad.
- Keep independent active selections for QCOM and USB-eGPU.
- Use the eGPU selection when the eGPU is available; otherwise use the QCOM selection.
- Fall back to Carrot's built-in model when a custom bundle is absent or invalid.
- Add Carrot-native settings panels for the standard and MICI UIs.
- Preserve Carrot model smoothing, control, rendering, and hardware diagnostics behavior.
- Add focused tests for parsing, download validation, slot selection, fallback, and UI state.
- Apply the completed change to both `carrot-wip` and `carrot-egpu` while the latter exists.

## Architecture

The port uses a small Carrot-owned model-manager package rather than importing the entire
sunnypilot feature tree. It keeps the sunnypilot catalog schema and selector-version gate, but
adapts paths, Params keys, messaging, and model loading to Carrot's current tree.

The offroad manager publishes catalog and download state to the UI. Selecting a bundle writes a
download request. Only after every artifact passes its advertised SHA-256 check is the relevant
QCOM or USB-eGPU active slot updated atomically.

At startup, modeld resolves the active hardware slot. A valid selected tinygrad pickle is loaded
from persistent storage; otherwise the checked-in Carrot model is used. eGPU failure does not
invalidate the independent QCOM slot.

## Safety and compatibility

- Model changes are offroad-only.
- HTTPS catalog/artifact locations and SHA-256 verification are required.
- Unknown selector versions, malformed bundles, path traversal, and unsupported runners are
  rejected.
- Partial downloads never become active.
- Existing Carrot eGPU detection and compiled-model fallback remain authoritative.
- No Carrot longitudinal/lateral control logic is replaced by sunnypilot logic.

## Verification

Run focused model-manager and modeld tests, Params/schema tests, standard and MICI UI import/tests,
then the repository's relevant lint/type checks. Validate both branches after applying the change.
