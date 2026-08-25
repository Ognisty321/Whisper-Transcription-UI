#!/usr/bin/env python3
"""Bootstrap the original XXL bytecode from a modernized external bundle."""

from __future__ import annotations

import json
import marshal
import os
import sqlite3
import ssl
import sys
import types
import warnings
from pathlib import Path


def _configure_dll_search(contents: Path) -> None:
    application_root = Path(sys.executable).resolve().parent
    candidates = [
        application_root,
        contents,
        contents / "ctranslate2",
        contents / "torch" / "lib",
        contents / "onnxruntime" / "capi",
        contents / "av.libs",
        contents / "numpy.libs",
        contents / "scipy.libs",
        contents / "pandas.libs",
    ]
    existing = [str(path) for path in candidates if path.is_dir()]
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        handles = []
        for path in existing:
            try:
                handles.append(os.add_dll_directory(path))
            except OSError:
                pass
        globals()["_XXL_DLL_DIRECTORY_HANDLES"] = handles


def _load_code(path: Path) -> types.CodeType:
    data = path.read_bytes()
    code = marshal.loads(data)
    if not isinstance(code, types.CodeType):
        raise TypeError(f"{path} does not contain a Python code object")
    return code


def _runtime_info(patch_metadata: dict[str, object]) -> dict[str, object]:
    import ctranslate2
    import huggingface_hub
    import numpy
    import onnxruntime
    import tokenizers
    import torch

    try:
        torch_arches = torch._C._cuda_getArchFlags()  # type: ignore[attr-defined]
    except Exception as exc:
        torch_arches = f"unavailable: {type(exc).__name__}: {exc}"

    info: dict[str, object] = {
        "release": "Faster-Whisper-XXL r245.4 comprehensive modernization",
        "python": sys.version,
        "openssl": ssl.OPENSSL_VERSION,
        "sqlite": sqlite3.sqlite_version,
        "ssl_module": getattr(ssl._ssl, "__file__", None),
        "sqlite_module": getattr(sqlite3, "__file__", None),
        "patches": patch_metadata,
        "versions": {
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "ctranslate2": ctranslate2.__version__,
            "onnxruntime_gpu": onnxruntime.__version__,
            "numpy": numpy.__version__,
            "tokenizers": tokenizers.__version__,
            "huggingface_hub": huggingface_hub.__version__,
        },
        "torch_compiled_arch_flags": torch_arches,
        "torch_cuda_available": torch.cuda.is_available(),
        "ctranslate2_cuda_device_count": ctranslate2.get_cuda_device_count(),
        "onnxruntime_available_providers": onnxruntime.get_available_providers(),
    }
    if torch.cuda.is_available():
        info["cuda_devices"] = [
            {
                "index": index,
                "name": torch.cuda.get_device_name(index),
                "capability": torch.cuda.get_device_capability(index),
            }
            for index in range(torch.cuda.device_count())
        ]
    return info


def _main() -> None:
    contents = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    scripts_dir = contents / "xxl_original_scripts"
    manifest_path = contents / "xxl_externalization_manifest.json"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing reconstruction manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    script_order = manifest.get("script_order")
    if not isinstance(script_order, list) or "__main__" not in script_order:
        raise RuntimeError("Invalid reconstruction manifest: script order is missing __main__")

    _configure_dll_search(contents)

    contents_text = str(contents)
    sys.path[:] = [
        item
        for item in sys.path
        if os.path.abspath(item or os.curdir) != os.path.abspath(contents_text)
    ]
    sys.path.insert(0, contents_text)

    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API.*",
        category=DeprecationWarning,
    )

    from xxl_runtime_patches import apply_runtime_patches

    patch_metadata = apply_runtime_patches(contents)
    globals()["_XXL_RUNTIME_PATCH_METADATA"] = patch_metadata

    if "--runtime-info" in sys.argv:
        print(json.dumps(_runtime_info(patch_metadata), ensure_ascii=False, indent=2))
        return

    namespace = globals()
    namespace["__name__"] = "__main__"
    namespace["__package__"] = None
    namespace["__cached__"] = None

    for script_name in script_order:
        script_path = scripts_dir / f"{script_name}.marshal"
        if not script_path.is_file():
            raise FileNotFoundError(f"Missing original script bytecode: {script_path}")
        namespace["__file__"] = str(contents / f"{script_name}.py")
        exec(_load_code(script_path), namespace, namespace)


if __name__ == "__main__":
    _main()
