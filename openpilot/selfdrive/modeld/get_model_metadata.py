#!/usr/bin/env python3
import sys
import pathlib
import codecs
import hashlib
import pickle
from typing import Any

from tinygrad.nn.onnx import OnnxPBParser
from openpilot.sunnypilot.navd.navigation_model_compat import verified_navigation_contract


class MetadataOnnxPBParser(OnnxPBParser):
  def _parse_ModelProto(self) -> dict:
    obj: dict[str, Any] = {"graph": {"input": [], "output": []}, "metadata_props": []}
    for fid, wire_type in self._parse_message(self.reader.len):
      match fid:
        case 7:
          obj["graph"] = self._parse_GraphProto()
        case 14:
          obj["metadata_props"].append(self._parse_StringStringEntryProto())
        case _:
          self.reader.skip_field(wire_type)
    return obj


def get_name_and_shape(value_info: dict[str, Any]) -> tuple[str, tuple[int, ...]]:
  shape = tuple(int(dim) if isinstance(dim, int) else 0 for dim in value_info["parsed_type"].shape)
  name = value_info["name"]
  return name, shape


def get_metadata_value_by_name(model: dict[str, Any], name: str) -> str | Any:
  for prop in model["metadata_props"]:
    if prop["key"] == name:
      return prop["value"]
  return None


def make_metadata_dict(model_path):
  model = MetadataOnnxPBParser(model_path).parse()
  output_slices = get_metadata_value_by_name(model, 'output_slices')
  assert output_slices is not None, 'output_slices not found in metadata'
  input_shapes = dict(get_name_and_shape(x) for x in model["graph"]["input"])
  with open(model_path, "rb") as file:
    model_sha256 = hashlib.file_digest(file, "sha256").hexdigest()
  navigation_feature_contract = verified_navigation_contract(
    input_shapes=input_shapes,
    model_sha256=model_sha256,
    declared_contract=get_metadata_value_by_name(model, 'navigation_feature_contract') or "",
    source_sha256=get_metadata_value_by_name(model, 'navigation_feature_source_sha256') or "",
  )
  return {
    'model_checkpoint': get_metadata_value_by_name(model, 'model_checkpoint'),
    'model_sha256': model_sha256,
    'navigation_feature_contract': navigation_feature_contract,
    'output_slices': pickle.loads(codecs.decode(output_slices.encode(), "base64")),
    'input_shapes': input_shapes,
    'output_shapes': dict(get_name_and_shape(x) for x in model["graph"]["output"]),
  }


if __name__ == "__main__":
  model_path = pathlib.Path(sys.argv[1])
  metadata_path = model_path.parent / (model_path.stem + '_metadata.pkl')
  with open(metadata_path, 'wb') as f:
    pickle.dump(make_metadata_dict(model_path), f)
  print(f'saved metadata to {metadata_path}')
