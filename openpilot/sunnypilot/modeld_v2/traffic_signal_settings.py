from pathlib import Path

# Experimental display-only setting. A marker is used instead of a Params key while this feature is
# being validated independently. /data persists across reboots, so the toggle remains sticky on the
# dedicated test branch without entering sunnypilot's normal settings backup/migration surface.
ENABLED_MARKER = Path("/data/traffic_signal_yolo_visuals.enabled")
STATE_PATH = Path("/dev/shm/sunnypilot_traffic_signal_yolo.json")


def is_enabled() -> bool:
  return ENABLED_MARKER.exists()


def set_enabled(enabled: bool) -> None:
  if enabled:
    ENABLED_MARKER.parent.mkdir(parents=True, exist_ok=True)
    ENABLED_MARKER.touch(exist_ok=True)
  else:
    ENABLED_MARKER.unlink(missing_ok=True)
    # Never leave a stale traffic-light indication visible after the feature is disabled.
    STATE_PATH.unlink(missing_ok=True)
