import asyncio
import hashlib
import os
import tempfile
from unittest import mock  # noqa: TID251

from openpilot.cereal import custom
from openpilot.common.file_chunker import get_chunk_name, get_manifest_path
from openpilot.selfdrive.modeld.model_manager.fetcher import ModelFetcher, ModelParser
from openpilot.selfdrive.modeld.model_manager.helpers import get_selected_bundle, resolve_bundle_by_ref
from openpilot.selfdrive.modeld.model_manager.manager import ModelManagerSP
from openpilot.selfdrive.modeld.model_manager.helpers import REQUIRED_TINYGRAD_REF


SHA = "1" * 64


def catalog(*bundles: dict, tinygrad_ref: str = REQUIRED_TINYGRAD_REF) -> dict:
  return {"tinygrad_ref": tinygrad_ref, "bundles": list(bundles)}


def manifest_bundle(ref: str = "test-ref", *, is_big: bool = False, version: int = 18) -> dict:
  return {
    "index": 1,
    "short_name": "TEST",
    "display_name": "Test Model",
    "generation": 12,
    "environment": "release",
    "runner": "tinygrad",
    "is_big": is_big,
    "is_20hz": True,
    "minimum_selector_version": str(version),
    "ref": ref,
    "models": [{
      "type": "chunked",
      "artifact": {
        "file_name": "driving_test_tinygrad.pkl",
        "download_uri": {"url": "https://example.com/driving_test_tinygrad.pkl", "sha256": SHA},
      },
    }],
  }


class TestModelParser:
  def test_valid_tinygrad_bundle(self):
    bundle, = ModelParser.parse_models(catalog(manifest_bundle()))
    assert bundle.ref == "test-ref"
    assert bundle.runner == custom.ModelManagerSP.Runner.tinygrad
    assert bundle.is20hz

  def test_wrong_selector_version_is_filtered(self):
    assert ModelParser.parse_models(catalog(manifest_bundle(version=17))) == []

  def test_wrong_tinygrad_revision_is_rejected(self):
    try:
      ModelParser.parse_models(catalog(manifest_bundle(), tinygrad_ref="0" * 40))
    except ValueError:
      pass
    else:
      raise AssertionError("a catalog compiled for another tinygrad revision must be rejected")

  def test_unsafe_filename_is_rejected(self):
    data = manifest_bundle()
    data["models"][0]["artifact"]["file_name"] = "../../etc/passwd"
    assert ModelParser.parse_models(catalog(data)) == []

  def test_non_https_artifact_is_rejected(self):
    data = manifest_bundle()
    data["models"][0]["artifact"]["download_uri"]["url"] = "http://example.com/model.pkl"
    assert ModelParser.parse_models(catalog(data)) == []

  def test_bad_hash_is_rejected(self):
    data = manifest_bundle()
    data["models"][0]["artifact"]["download_uri"]["sha256"] = "bad"
    assert ModelParser.parse_models(catalog(data)) == []


class TestModelSources:
  @staticmethod
  def bundle(ref: str):
    bundle = custom.ModelManagerSP.ModelBundle.new_message()
    bundle.ref = ref
    bundle.minimumSelectorVersion = 18
    return bundle

  def test_ref_resolves_to_independent_slot(self):
    qcom = self.bundle("qcom-ref")
    usbgpu = self.bundle("egpu-ref")
    assert resolve_bundle_by_ref("qcom-ref", {"qcom": [qcom], "usbgpu": [usbgpu]}) == (qcom, "qcom")
    assert resolve_bundle_by_ref("egpu-ref", {"qcom": [qcom], "usbgpu": [usbgpu]}) == (usbgpu, "usbgpu")

  def test_selected_bundle_is_per_slot(self):
    qcom = self.bundle("qcom-ref").to_dict()
    usbgpu = self.bundle("egpu-ref").to_dict()
    params = mock.MagicMock()
    params.get.side_effect = lambda key: {
      "ModelManager_ActiveBundle": qcom,
      "ModelManager_ActiveBundleUSBGPU": usbgpu,
    }.get(key)
    assert get_selected_bundle(params, "qcom").ref == "qcom-ref"
    assert get_selected_bundle(params, "usbgpu").ref == "egpu-ref"

  def test_active_source_tracks_egpu(self):
    assert ModelFetcher.active_source(False) == "qcom"
    assert ModelFetcher.active_source(True) == "usbgpu"


class TestModelDownloads:
  def setup_method(self):
    self.manager = ModelManagerSP.__new__(ModelManagerSP)
    self.manager.params = mock.MagicMock()
    self.manager.params.get.return_value = "test-ref"
    self.manager.pm = mock.MagicMock()
    self.manager.selected_bundle = None
    self.manager.selected_source = ""
    self.manager.active_bundle = None
    self.manager.available_models = []
    self.manager.source_models = {}
    self.manager.chestnut_present = False
    self.manager._chunk_size = 16
    self.manager._download_start_times = {}

  def test_whole_file_hash_is_verified_before_activation(self):
    body = b"verified model"
    bundle = custom.ModelManagerSP.ModelBundle.new_message()
    bundle.ref = "test-ref"
    bundle.minimumSelectorVersion = 18
    bundle.runner = custom.ModelManagerSP.Runner.tinygrad
    bundle.init("models", 1)
    artifact = bundle.models[0].artifact
    artifact.fileName = "driving_test_tinygrad.pkl"
    artifact.downloadUri.uri = "https://example.com/model.pkl"
    artifact.downloadUri.sha256 = hashlib.sha256(body).hexdigest()

    response = mock.MagicMock()
    response.__enter__.return_value = response
    response.headers = {"content-length": str(len(body))}
    response.iter_content.return_value = [body]

    store = {}
    self.manager.params.put.side_effect = lambda key, value, **kwargs: store.__setitem__(key, value)
    with tempfile.TemporaryDirectory() as destination, mock.patch(
      "openpilot.selfdrive.modeld.model_manager.manager.requests.get", return_value=response,
    ):
      asyncio.run(self.manager._download_bundle(bundle, destination, "qcom"))
      with open(os.path.join(destination, artifact.fileName), "rb") as f:
        assert f.read() == body

    assert "ModelManager_ActiveBundle" in store
    assert "ModelManager_ActiveBundleUSBGPU" not in store

  def test_failed_hash_leaves_slot_unchanged_and_removes_partial(self):
    bundle = custom.ModelManagerSP.ModelBundle.new_message()
    bundle.ref = "bad-ref"
    bundle.minimumSelectorVersion = 18
    bundle.runner = custom.ModelManagerSP.Runner.tinygrad
    bundle.init("models", 1)
    artifact = bundle.models[0].artifact
    artifact.fileName = "bad.pkl"
    artifact.downloadUri.uri = "https://example.com/bad.pkl"
    artifact.downloadUri.sha256 = SHA

    response = mock.MagicMock()
    response.__enter__.return_value = response
    response.headers = {"content-length": "3"}
    response.iter_content.return_value = [b"bad"]

    with tempfile.TemporaryDirectory() as destination, mock.patch(
      "openpilot.selfdrive.modeld.model_manager.manager.requests.get", return_value=response,
    ):
      try:
        asyncio.run(self.manager._download_bundle(bundle, destination, "usbgpu"))
      except ValueError:
        pass
      else:
        raise AssertionError("hash mismatch must fail")
      assert not os.path.exists(os.path.join(destination, artifact.fileName))

    written_keys = [call.args[0] for call in self.manager.params.put.call_args_list]
    assert "ModelManager_ActiveBundleUSBGPU" not in written_keys

  def test_chunk_manifest_names_match_file_chunker(self):
    base = "/tmp/model.pkl"
    assert get_chunk_name(base, 0, 2).endswith(".chunk01of02")
    assert get_manifest_path(base).endswith(".chunkmanifest")
