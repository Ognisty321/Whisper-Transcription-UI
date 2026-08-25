#!/usr/bin/env python3
"""Verify the reconstructed XXL bundle's selected GPU/runtime packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def version_starts(value: str, expected: str, name: str) -> None:
    if not value.startswith(expected):
        raise RuntimeError(f"Unexpected {name} version: {value!r}; expected prefix {expected!r}")


def ensure_inside(module_file: str | None, root: Path, name: str) -> str:
    if not module_file:
        raise RuntimeError(f"{name} does not expose __file__")
    resolved = Path(module_file).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"{name} loaded outside bundle: {resolved}") from exc
    return str(resolved)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contents_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    contents = args.contents_dir.resolve()
    if not contents.is_dir():
        raise NotADirectoryError(contents)

    dll_dirs = [
        contents,
        contents / "ctranslate2",
        contents / "torch" / "lib",
        contents / "onnxruntime" / "capi",
    ]
    existing = [path for path in dll_dirs if path.is_dir()]
    os.environ["PATH"] = os.pathsep.join([str(path) for path in existing] + [os.environ.get("PATH", "")])
    handles = []
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        handles = [os.add_dll_directory(str(path)) for path in existing]

    sys.path.insert(0, str(contents))

    import ctranslate2
    import onnxruntime
    import torch
    import torchaudio
    import torchvision

    versions = {
        "python": sys.version,
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "torchvision": torchvision.__version__,
        "torchaudio": torchaudio.__version__,
        "ctranslate2": ctranslate2.__version__,
        "onnxruntime_gpu": onnxruntime.__version__,
    }

    version_starts(versions["torch"], "2.11.0", "torch")
    if versions["torch_cuda"] != "12.8":
        raise RuntimeError(f"Unexpected torch CUDA runtime: {versions['torch_cuda']!r}; expected '12.8'")
    version_starts(versions["torchvision"], "0.26.0", "torchvision")
    version_starts(versions["torchaudio"], "2.11.0", "torchaudio")
    if versions["ctranslate2"] != "4.8.1":
        raise RuntimeError(f"Unexpected CTranslate2 version: {versions['ctranslate2']!r}")
    if versions["onnxruntime_gpu"] != "1.23.2":
        raise RuntimeError(f"Unexpected ONNX Runtime version: {versions['onnxruntime_gpu']!r}")

    module_files = {
        "torch": ensure_inside(torch.__file__, contents, "torch"),
        "torchvision": ensure_inside(torchvision.__file__, contents, "torchvision"),
        "torchaudio": ensure_inside(torchaudio.__file__, contents, "torchaudio"),
        "ctranslate2": ensure_inside(ctranslate2.__file__, contents, "ctranslate2"),
        "onnxruntime": ensure_inside(onnxruntime.__file__, contents, "onnxruntime"),
    }

    try:
        compiled_arch_flags = torch._C._cuda_getArchFlags()  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - diagnostic only
        raise RuntimeError(f"Unable to read PyTorch CUDA architecture flags: {exc}") from exc
    if "sm_120" not in compiled_arch_flags.split():
        raise RuntimeError(f"PyTorch runtime does not include Blackwell sm_120: {compiled_arch_flags!r}")

    cudnn_version = torch.backends.cudnn.version()
    if not isinstance(cudnn_version, int) or cudnn_version < 90000:
        raise RuntimeError(f"Expected cuDNN 9 or newer, got {cudnn_version!r}")

    onnxruntime_providers = onnxruntime.get_available_providers()
    if "CUDAExecutionProvider" not in onnxruntime_providers:
        raise RuntimeError(f"ONNX Runtime CUDAExecutionProvider is unavailable: {onnxruntime_providers!r}")

    critical_files = [
        contents / "ctranslate2" / "_ext.cp310-win_amd64.pyd",
        contents / "ctranslate2" / "ctranslate2.dll",
        contents / "torch" / "lib" / "torch_cuda.dll",
        contents / "torch" / "lib" / "cublas64_12.dll",
        contents / "torch" / "lib" / "cublasLt64_12.dll",
        contents / "torch" / "lib" / "cudart64_12.dll",
        contents / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll",
    ]
    missing = [str(path) for path in critical_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing critical runtime files: {missing}")

    report: dict[str, Any] = {
        "versions": versions,
        "module_files": module_files,
        "torch_cuda_available_on_runner": torch.cuda.is_available(),
        "torch_compiled_arch_flags": compiled_arch_flags,
        "torch_blackwell_sm120_present": True,
        "torch_cudnn_version": cudnn_version,
        "ctranslate2_cuda_device_count_on_runner": ctranslate2.get_cuda_device_count(),
        "onnxruntime_available_providers": onnxruntime_providers,
        "onnxruntime_cuda_provider_present": True,
        "dll_search_dirs": [str(path) for path in existing],
        "critical_files": {
            str(path.relative_to(contents)): {
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in critical_files
        },
    }

    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")

    # Keep os.add_dll_directory handles alive until all imports and checks finish.
    _ = handles
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
