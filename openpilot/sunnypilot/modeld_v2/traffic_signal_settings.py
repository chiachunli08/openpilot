from pathlib import Path

# Experimental display-only setting. Kept outside Params until the feature is validated on-road.
# /data persists across reboots but this marker is intentionally not part of settings backup/migration.
ENABLED_MARKER = Path("/data/traffic_signal_yolo_visuals.enabled")


def is_enabled() -> bool:
  return ENABLED_MARKER.exists()


def set_enabled(enabled: bool) -> None:
  if enabled:
    ENABLED_MARKER.parent.mkdir(parents=True, exist_ok=True)
    ENABLED_MARKER.touch(exist_ok=True)
  else:
    ENABLED_MARKER.unlink(missing_ok=True)
