from __future__ import annotations

import math


NAV_FEATURE_LEN = 64
NAV_FEATURE_KEYS = {"nav_features", "navigation_features", "navfeatures", "navigationfeatures"}
TACO2_NAVMODEL_SHA256 = "f851f19b0a9e2299639f18856e4879ee863918227b7cef6a07eb6b94a273a9aa"
TACO2_DRIVING_MODEL_SHA256 = "f794d65ddfb3600e0b3f7d7e894d1dd278b88569de863aae41246eec43f035cf"
TACO2_NAV_FEATURE_CONTRACT = "comma-taco2-a8c957e9-navmodel-f851f19b-features64-v1"


def navigation_feature_input_key(input_shapes: dict[str, tuple | list]) -> str | None:
  """Find one structurally plausible 64-value navigation input.

  This is sufficient for compiler plumbing and zero initialization only. It is
  deliberately not evidence that the model learned taco2's feature semantics.
  """
  matches = []
  for key, shape in input_shapes.items():
    normalized = key.lower().replace("-", "_")
    if normalized in NAV_FEATURE_KEYS and math.prod(int(v) for v in shape) == NAV_FEATURE_LEN:
      matches.append(key)
  return matches[0] if len(matches) == 1 else None


def verified_navigation_contract(*, input_shapes: dict[str, tuple | list], model_sha256: str = "",
                                 declared_contract: str = "", source_sha256: str = "") -> str:
  """Resolve a traceable taco2 feature contract from model identity/metadata."""
  if navigation_feature_input_key(input_shapes) is None:
    return ""
  if model_sha256 == TACO2_DRIVING_MODEL_SHA256:
    return TACO2_NAV_FEATURE_CONTRACT
  if declared_contract == TACO2_NAV_FEATURE_CONTRACT and source_sha256 == TACO2_NAVMODEL_SHA256:
    return TACO2_NAV_FEATURE_CONTRACT
  return ""


def navigation_feature_key(input_shapes: dict[str, tuple | list], contract: str = "") -> str | None:
  """Return the input only when both its shape and learned-feature contract match."""
  if contract != TACO2_NAV_FEATURE_CONTRACT:
    return None
  return navigation_feature_input_key(input_shapes)


def navigation_features_fresh(recv_time_ns: int, now_ns: int, max_age_sec: float = 2.5) -> bool:
  return recv_time_ns > 0 and 0 <= now_ns - recv_time_ns <= int(max_age_sec * 1e9)
