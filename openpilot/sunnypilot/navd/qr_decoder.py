"""Optional, independently installed ZXing-C++ decoder. Images never leave the device."""
import hashlib
import importlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from urllib.request import urlopen

VERSION = "3.1.1"
WHEELS = {
  "aarch64": ("0d/f3/3fb2c6c48e6f58382fbbd31965c7caafd81f75b7e6707b011bdb940adb5f/" +
              "zxing_cpp-3.1.1-cp312-abi3-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl",
              "f4dae01111f323f46736fc21f05c14dcaaac06cea5fdc8fd994ba19f6f918c6e"),
  "x86_64": ("0c/30/79683cf7139ee5325fbc68169eb8dc1cb2033ec43339b5f39de990f909a7/" +
             "zxing_cpp-3.1.1-cp312-abi3-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
             "9cf67341949946307d086b302cefd453fb47bc6d6ddc7d088839e9481982757b"),
}
_install_lock = threading.Lock()


def load_decoder(root):
  package = (Path(root) / "current" / "zxingcpp").resolve()
  if not (package / "__init__.py").is_file():
    return importlib.import_module("zxingcpp")
  name = "_sunnypilot_zxing_" + hashlib.sha256(str(package).encode()).hexdigest()[:16]
  if name not in sys.modules:
    spec = importlib.util.spec_from_file_location(name, package / "__init__.py", submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
      spec.loader.exec_module(module)
    except Exception:
      sys.modules.pop(name, None)
      raise
  return sys.modules[name]


def install_decoder(root, cancelled=lambda: False):
  if platform.system() != "Linux" or platform.machine() not in WHEELS or sys.version_info < (3, 12) or platform.python_implementation() != "CPython":
    raise RuntimeError("unsupported")
  with _install_lock:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="zxing-", dir=root))
    pointer = root / (stage.name + ".link")
    activated = False
    try:
      filename, expected = WHEELS[platform.machine()]
      wheel = stage / "decoder.whl"
      digest = hashlib.sha256()
      size = 0
      with urlopen("https://files.pythonhosted.org/packages/" + filename, timeout=15) as response, wheel.open("wb") as output:
        while chunk := response.read(65536):
          if cancelled():
            raise RuntimeError("cancelled")
          size += len(chunk)
          if size > 4 * 1024 * 1024:
            raise RuntimeError("integrity")
          digest.update(chunk)
          output.write(chunk)
      if digest.hexdigest() != expected:
        raise RuntimeError("integrity")
      with zipfile.ZipFile(wheel) as archive:
        if sum(i.file_size for i in archive.infolist()) > 32 * 1024 * 1024:
          raise RuntimeError("integrity")
        for name in archive.namelist():
          if Path(name).is_absolute() or ".." in Path(name).parts:
            raise RuntimeError("integrity")
        archive.extractall(stage)
      wheel.unlink()
      subprocess.run([sys.executable, "-I", "-c",
                      "import sys; sys.path.insert(0, sys.argv[1]); import zxingcpp; assert callable(zxingcpp.read_barcodes)",
                      str(stage)], check=True, capture_output=True, timeout=20)
      if cancelled():
        raise RuntimeError("cancelled")
      pointer.symlink_to(stage.name, target_is_directory=True)
      os.replace(pointer, root / "current")
      activated = True
    finally:
      pointer.unlink(missing_ok=True)
      if not activated:
        shutil.rmtree(stage, ignore_errors=True)
  return VERSION
