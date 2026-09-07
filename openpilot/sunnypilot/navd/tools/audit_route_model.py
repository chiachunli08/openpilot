#!/usr/bin/env python3
"""Inspect a local ONNX model for possible navigation inputs; never run it.

An input name/shape or graph dependency cannot prove encoder compatibility.
Actual route conditioning requires weights trained with that input contract.
"""
import argparse
import hashlib
import json
from pathlib import Path


def inspect_graph(model):
  def dimensions(value):
    return [d.dim_value if d.HasField("dim_value") else (d.dim_param or None) for d in value.type.tensor_type.shape.dim]

  initializers = {value.name for value in model.graph.initializer}
  inputs = {value.name: {"shape": dimensions(value), "onnx_dtype": value.type.tensor_type.elem_type}
            for value in model.graph.input if value.name not in initializers}
  navigation = [name for name in inputs if any(token in name.lower() for token in ("nav", "route", "map"))]
  # Inspect direct, topologically ordered data flow only. Control-flow graphs
  # have implicit captures; do not infer compatibility from this simple walk.
  nested_graph = any(attribute.type in (5, 10) for node in model.graph.node for attribute in node.attribute)
  dependencies = {}
  for name in navigation:
    reached = {name}
    for node in model.graph.node:
      if any(value in reached for value in node.input):
        reached.update(node.output)
    dependencies[name] = [value.name for value in model.graph.output if value.name in reached]
  status = "no_named_navigation_input" if not navigation else "requires_paired_encoder_and_weight_validation"
  return {"inputs": inputs, "navigation_input_candidates": navigation, "direct_output_dependencies": dependencies,
          "has_nested_graph": nested_graph, "status": status, "model_input_ready": False}


def audit(path):
  import onnx
  path = Path(path)
  with path.open("rb") as stream:
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
  return {"file": path.name, "sha256": digest, **inspect_graph(onnx.load(path, load_external_data=False))}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("models", nargs="+", type=Path)
  args = parser.parse_args()
  print(json.dumps([audit(path) for path in args.models], ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
  main()
