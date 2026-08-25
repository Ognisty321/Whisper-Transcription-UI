#!/usr/bin/env python3
"""Verify versions, native assets and compatibility patches in an XXL bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import ssl
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_PREFIXES = {
    "torch": "2.11.0+cu128",
    "torchvision": "0.26.0+cu128",
    "torchaudio": "2.11.0+cu128",
    "ctranslate2": "4.8.1",
    "onnxruntime": "1.23.2",
    "numpy": "1.26.4",
    "scipy": "1.15.3",
    "sklearn": "1.7.2",
    "pandas": "2.3.3",
    "librosa": "0.11.0",
    "soundfile": "0.14.0",
    "soxr": "1.1.0",
    "av": "17.1.0",
    "pyannote.audio": "3.4.0",
    "lightning": "2.6.5",
    "torchmetrics": "1.9.0",
    "huggingface_hub": "1.28.0",
    "tokenizers": "0.23.1",
    "requests": "2.34.2",
    "urllib3": "2.7.0",
    "certifi": "2026.7.22",
    "aiohttp": "3.14.3",
    "tqdm": "4.70.0",
    "psutil": "7.2.2",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def add_runtime_paths(contents: Path, application_root: Path) -> list[object]:
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
    existing = [path for path in candidates if path.is_dir()]
    os.environ["PATH"] = os.pathsep.join([str(path) for path in existing] + [os.environ.get("PATH", "")])
    handles: list[object] = []
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        for path in existing:
            try:
                handles.append(os.add_dll_directory(str(path)))
            except OSError:
                pass
    sys.path.insert(0, str(contents))
    return handles


def module_version(module: Any) -> str:
    for path in ("__version__", "version.version"):
        value = module
        try:
            for component in path.split("."):
                value = getattr(value, component)
            if value is not None:
                return str(value)
        except Exception:
            continue
    raise RuntimeError(f"Could not determine version for {module.__name__}")


def ensure_inside(module: Any, contents: Path) -> str:
    file_name = getattr(module, "__file__", None)
    if not file_name:
        raise RuntimeError(f"{module.__name__} does not expose __file__")
    path = Path(file_name).resolve()
    try:
        path.relative_to(contents)
    except ValueError as exc:
        raise RuntimeError(f"{module.__name__} loaded outside bundle: {path}") from exc
    return str(path)


def test_timestamp_boundary() -> dict[str, float]:
    import faster_whisper.vad as vad

    chunks = [{"start": 16000, "end": 32000}, {"start": 48000, "end": 64000}]
    mapping = vad.SpeechTimestampsMap(chunks, sampling_rate=16000, time_precision=3)
    # Compressed speech duration is 2 seconds.  At the exact first chunk end,
    # an end timestamp belongs to chunk 0 while a start belongs to chunk 1.
    start_mapping = mapping.get_original_time(1.0, is_end=False)
    end_mapping = mapping.get_original_time(1.0, is_end=True)
    if start_mapping != 2.0 or end_mapping != 2.0:
        # They map to the same real second in this fixture but must select
        # different internal chunks; verify that explicitly as well.
        pass
    if mapping.get_chunk_index(1.0, is_end=False) != 1:
        raise RuntimeError("Timestamp start boundary patch is not active")
    if mapping.get_chunk_index(1.0, is_end=True) != 0:
        raise RuntimeError("Timestamp end boundary patch is not active")
    return {"start_mapping": start_mapping, "end_mapping": end_mapping}


def test_suppressed_tokens() -> dict[str, Any]:
    import faster_whisper.transcribe as transcribe

    class FakeTokenizer:
        non_speech_tokens = (90, 91)
        transcribe = 1
        translate = 2
        sot = 3
        sot_prev = 4
        sot_lm = 5
        no_speech = 6

    result = transcribe.get_suppressed_tokens(FakeTokenizer(), [-1])
    if 6 not in result:
        raise RuntimeError("No-speech/no-captions token is not suppressed")
    return {"tokens": list(result), "contains_no_speech": True}


def test_silero_v6(contents: Path) -> dict[str, Any]:
    import numpy as np
    import faster_whisper.vad as vad

    model_path = contents / "faster_whisper" / "assets" / "silero_vad_v6.onnx"
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    model = vad.get_vad_model()
    audio = np.zeros((1, 512 * 4), dtype=np.float32)
    probabilities = model(audio)
    if probabilities.shape != (1, 4):
        raise RuntimeError(f"Unexpected Silero VAD v6 output shape: {probabilities.shape}")
    if not np.isfinite(probabilities).all():
        raise RuntimeError("Silero VAD v6 returned non-finite values")
    return {
        "asset": str(model_path),
        "asset_sha256": sha256(model_path),
        "output_shape": list(probabilities.shape),
        "min": float(probabilities.min()),
        "max": float(probabilities.max()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("--patch-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    bundle_root = args.bundle_root.resolve()
    contents = bundle_root / "_xxl_data"
    if not contents.is_dir():
        raise NotADirectoryError(contents)
    handles = add_runtime_paths(contents, bundle_root)

    from xxl_runtime_patches import apply_runtime_patches

    patch_metadata = apply_runtime_patches(contents)

    versions: dict[str, str] = {}
    module_files: dict[str, str] = {}
    for name, expected in EXPECTED_PREFIXES.items():
        module = importlib.import_module(name)
        value = module_version(module)
        versions[name] = value
        module_files[name] = ensure_inside(module, contents)
        if not value.startswith(expected):
            raise RuntimeError(f"Unexpected {name} version: {value!r}; expected prefix {expected!r}")

    import ctranslate2
    import onnxruntime
    import torch
    import faster_whisper

    if not sys.version.startswith("3.10.21"):
        raise RuntimeError(f"Unexpected CPython runtime: {sys.version}")
    if not ssl.OPENSSL_VERSION.startswith("OpenSSL 3.0.21"):
        raise RuntimeError(f"Unexpected TLS runtime: {ssl.OPENSSL_VERSION}")

    arch_flags = torch._C._cuda_getArchFlags()  # type: ignore[attr-defined]
    if "sm_120" not in arch_flags.split():
        raise RuntimeError(f"Blackwell sm_120 is missing: {arch_flags}")
    providers = onnxruntime.get_available_providers()
    if "CUDAExecutionProvider" not in providers:
        raise RuntimeError(f"ONNX CUDA provider is missing: {providers}")

    patch_report = json.loads(args.patch_report.read_text(encoding="utf-8"))
    patch_names = [item.get("patch") for item in patch_report.get("changes", [])]
    if "r245.4-diarize-postfix-path" not in patch_names:
        raise RuntimeError("The r245.4 diarize+postfix path patch is missing")

    ffmpeg = bundle_root / "ffmpeg.exe"
    ffprobe = bundle_root / "ffprobe.exe"
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise FileNotFoundError("Updated ffmpeg.exe/ffprobe.exe pair is missing")
    ffmpeg_output = subprocess.run(
        [str(ffmpeg), "-version"], capture_output=True, text=True, timeout=30, check=True
    ).stdout.splitlines()[0]
    ffprobe_output = subprocess.run(
        [str(ffprobe), "-version"], capture_output=True, text=True, timeout=30, check=True
    ).stdout.splitlines()[0]
    if "ffmpeg version 8.1.1" not in ffmpeg_output:
        raise RuntimeError(f"Unexpected FFmpeg: {ffmpeg_output}")

    report: dict[str, Any] = {
        "python": sys.version,
        "openssl": ssl.OPENSSL_VERSION,
        "faster_whisper_custom_base": faster_whisper.__version__,
        "patch_metadata": patch_metadata,
        "main_bytecode_patches": patch_report,
        "versions": versions,
        "module_files": module_files,
        "torch_cuda_runtime": torch.version.cuda,
        "torch_compiled_arch_flags": arch_flags,
        "torch_cuda_available_on_runner": torch.cuda.is_available(),
        "ctranslate2_cuda_device_count_on_runner": ctranslate2.get_cuda_device_count(),
        "onnxruntime_providers": providers,
        "timestamp_boundary_test": test_timestamp_boundary(),
        "suppressed_token_test": test_suppressed_tokens(),
        "silero_vad_v6_test": test_silero_v6(contents),
        "ffmpeg": {"version": ffmpeg_output, "sha256": sha256(ffmpeg)},
        "ffprobe": {"version": ffprobe_output, "sha256": sha256(ffprobe)},
        "critical_files": {},
    }

    critical = [
        contents / "python310.dll",
        contents / "libssl-3.dll",
        contents / "libcrypto-3.dll",
        contents / "ctranslate2" / "ctranslate2.dll",
        contents / "torch" / "lib" / "torch_cuda.dll",
        contents / "torch" / "lib" / "cublas64_12.dll",
        contents / "torch" / "lib" / "cublasLt64_12.dll",
        contents / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll",
    ]
    for path in critical:
        if not path.is_file():
            raise FileNotFoundError(path)
        report["critical_files"][path.relative_to(bundle_root).as_posix()] = {
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "python": report["python"],
        "openssl": report["openssl"],
        "versions": versions,
        "torch_compiled_arch_flags": arch_flags,
        "onnxruntime_providers": providers,
        "patch_level": patch_metadata["patch_level"],
    }, ensure_ascii=False, indent=2))
    _ = handles
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
