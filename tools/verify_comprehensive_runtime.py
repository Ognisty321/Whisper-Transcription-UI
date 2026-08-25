#!/usr/bin/env python3
"""Verify the fully modernized Faster-Whisper-XXL Windows runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import sqlite3
import ssl
import subprocess
import sys
from pathlib import Path
from typing import Any


EXPECTED_DISTRIBUTIONS = {
    "torch": "2.11.0+cu128",
    "torchvision": "0.26.0+cu128",
    "torchaudio": "2.11.0+cu128",
    "ctranslate2": "4.8.1",
    "onnxruntime-gpu": "1.23.2",
    "huggingface-hub": "1.28.0",
    "tokenizers": "0.23.1",
    "av": "17.1.0",
    "tqdm": "4.70.0",
    "numpy": "1.26.4",
    "scipy": "1.15.3",
    "scikit-learn": "1.7.2",
    "pandas": "2.3.3",
    "librosa": "0.11.0",
    "soundfile": "0.14.0",
    "soxr": "1.1.0",
    "auditok": "0.5.2",
    "rotary-embedding-torch": "0.9.1",
    "beartype": "0.22.9",
    "ml-collections": "1.1.0",
    "webrtcvad-wheels": "2.0.14",
    "pydub": "0.25.1",
    "PyAudio": "0.2.14",
    "pyreadline3": "3.5.4",
    "pyannote.audio": "3.4.0",
    "lightning": "2.6.5",
    "pytorch-lightning": "2.6.5",
    "torchmetrics": "1.9.0",
    "lightning-utilities": "0.15.3",
    "omegaconf": "2.3.1",
    "antlr4-python3-runtime": "4.9.3",
    "docopt": "0.6.2",
    "optuna": "4.9.0",
    "sqlalchemy": "2.0.52",
    "requests": "2.34.2",
    "urllib3": "2.7.0",
    "certifi": "2026.7.22",
    "charset-normalizer": "3.5.1",
    "idna": "3.19",
    "aiohttp": "3.14.3",
    "yarl": "1.24.5",
    "multidict": "6.7.1",
    "frozenlist": "1.8.0",
    "attrs": "26.1.0",
    "filelock": "3.32.4",
    "fsspec": "2026.7.0",
    "jinja2": "3.1.6",
    "markupsafe": "3.0.3",
    "networkx": "3.4.2",
    "sympy": "1.14.0",
    "typing-extensions": "4.16.0",
    "packaging": "26.3",
    "pyyaml": "6.0.3",
    "psutil": "7.2.2",
    "sentencepiece": "0.2.2",
    "cffi": "2.1.1",
    "matplotlib": "3.10.9",
    "pillow": "12.3.0",
    "setuptools": "81.0.0",
    "wheel": "0.48.0",
}

KEY_IMPORTS = {
    "torch": "torch",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
    "ctranslate2": "ctranslate2",
    "onnxruntime-gpu": "onnxruntime",
    "huggingface-hub": "huggingface_hub",
    "tokenizers": "tokenizers",
    "av": "av",
    "numpy": "numpy",
    "scipy": "scipy",
    "scikit-learn": "sklearn",
    "pandas": "pandas",
    "librosa": "librosa",
    "soundfile": "soundfile",
    "soxr": "soxr",
    "auditok": "auditok",
    "rotary-embedding-torch": "rotary_embedding_torch",
    "beartype": "beartype",
    "ml-collections": "ml_collections",
    "webrtcvad-wheels": "webrtcvad",
    "PyAudio": "pyaudio",
    "pyannote.audio": "pyannote.audio",
    "lightning": "lightning",
    "pytorch-lightning": "pytorch_lightning",
    "torchmetrics": "torchmetrics",
    "omegaconf": "omegaconf",
    "optuna": "optuna",
    "requests": "requests",
    "aiohttp": "aiohttp",
    "matplotlib": "matplotlib",
    "pillow": "PIL",
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
    os.environ["PATH"] = os.pathsep.join(
        [str(path) for path in existing] + [os.environ.get("PATH", "")]
    )
    handles: list[object] = []
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        for path in existing:
            try:
                handles.append(os.add_dll_directory(str(path)))
            except OSError:
                pass
    sys.path.insert(0, str(contents))
    return handles


def ensure_inside(module: Any, contents: Path) -> str:
    filename = getattr(module, "__file__", None)
    if not filename:
        raise RuntimeError(f"{module.__name__} does not expose __file__")
    path = Path(filename).resolve()
    try:
        path.relative_to(contents)
    except ValueError as exc:
        raise RuntimeError(f"{module.__name__} loaded outside bundle: {path}") from exc
    return str(path)


def test_timestamp_boundary() -> dict[str, Any]:
    import faster_whisper.vad as vad

    chunks = [{"start": 16000, "end": 32000}, {"start": 48000, "end": 64000}]
    mapping = vad.SpeechTimestampsMap(chunks, sampling_rate=16000, time_precision=3)
    start_index = mapping.get_chunk_index(1.0, is_end=False)
    end_index = mapping.get_chunk_index(1.0, is_end=True)
    if start_index != 1 or end_index != 0:
        raise RuntimeError(
            f"Timestamp boundary backport is inactive: start={start_index}, end={end_index}"
        )
    return {
        "start_chunk_index": start_index,
        "end_chunk_index": end_index,
        "start_time": mapping.get_original_time(1.0, is_end=False),
        "end_time": mapping.get_original_time(1.0, is_end=True),
    }


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
        raise RuntimeError("No-speech/no-captions suppression backport is inactive")
    return {"tokens": list(result), "contains_no_speech": True}


def test_silero_v6(contents: Path) -> dict[str, Any]:
    import numpy as np
    import faster_whisper.vad as vad

    model_path = contents / "faster_whisper" / "assets" / "silero_vad_v6.onnx"
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    model = vad.get_vad_model()
    probabilities = model(np.zeros((1, 512 * 4), dtype=np.float32))
    if probabilities.shape != (1, 4):
        raise RuntimeError(f"Unexpected Silero VAD v6 shape: {probabilities.shape}")
    if not np.isfinite(probabilities).all():
        raise RuntimeError("Silero VAD v6 returned non-finite values")
    return {
        "asset": str(model_path),
        "asset_sha256": sha256(model_path),
        "shape": list(probabilities.shape),
        "minimum": float(probabilities.min()),
        "maximum": float(probabilities.max()),
    }


def command_version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "-version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.splitlines()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("--patch-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-openssl", default="OpenSSL 3.5.7")
    parser.add_argument("--expected-sqlite", default="3.53.4")
    parser.add_argument("--expected-ffmpeg", default="ffmpeg version 9.0")
    args = parser.parse_args()

    bundle_root = args.bundle_root.resolve()
    contents = bundle_root / "_xxl_data"
    if not contents.is_dir():
        raise NotADirectoryError(contents)
    handles = add_runtime_paths(contents, bundle_root)

    from xxl_runtime_patches import apply_runtime_patches

    patch_metadata = apply_runtime_patches(contents)

    versions: dict[str, str] = {}
    for distribution, expected in EXPECTED_DISTRIBUTIONS.items():
        value = importlib.metadata.version(distribution)
        versions[distribution] = value
        if value != expected:
            raise RuntimeError(
                f"Unexpected {distribution} version: {value!r}; expected {expected!r}"
            )

    module_files: dict[str, str] = {}
    for distribution, module_name in KEY_IMPORTS.items():
        module = importlib.import_module(module_name)
        module_files[distribution] = ensure_inside(module, contents)

    import ctranslate2
    import faster_whisper
    import onnxruntime
    import torch

    if not sys.version.startswith("3.10.21"):
        raise RuntimeError(f"Unexpected CPython runtime: {sys.version}")
    if not ssl.OPENSSL_VERSION.startswith(args.expected_openssl):
        raise RuntimeError(
            f"Unexpected TLS runtime: {ssl.OPENSSL_VERSION!r}; expected {args.expected_openssl!r}"
        )
    if sqlite3.sqlite_version != args.expected_sqlite:
        raise RuntimeError(
            f"Unexpected SQLite runtime: {sqlite3.sqlite_version!r}; expected {args.expected_sqlite!r}"
        )

    arch_flags = torch._C._cuda_getArchFlags()  # type: ignore[attr-defined]
    if "sm_120" not in arch_flags.split():
        raise RuntimeError(f"Blackwell sm_120 is missing: {arch_flags}")
    providers = onnxruntime.get_available_providers()
    if "CUDAExecutionProvider" not in providers:
        raise RuntimeError(f"ONNX Runtime CUDA provider is missing: {providers}")

    patch_report = json.loads(args.patch_report.read_text(encoding="utf-8"))
    patch_names = [item.get("patch") for item in patch_report.get("changes", [])]
    if "r245.4-diarize-postfix-path" not in patch_names:
        raise RuntimeError("The r245.4 diarize+postfix path patch is missing")

    ffmpeg = bundle_root / "ffmpeg.exe"
    ffprobe = bundle_root / "ffprobe.exe"
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise FileNotFoundError("Updated ffmpeg.exe/ffprobe.exe pair is missing")
    ffmpeg_version = command_version(ffmpeg)
    ffprobe_version = command_version(ffprobe)
    if args.expected_ffmpeg not in ffmpeg_version:
        raise RuntimeError(
            f"Unexpected FFmpeg: {ffmpeg_version!r}; expected marker {args.expected_ffmpeg!r}"
        )

    forbidden = [contents / "libssl-1_1.dll", contents / "libcrypto-1_1.dll"]
    stale = [str(path) for path in forbidden if path.exists()]
    if stale:
        raise RuntimeError(f"Obsolete OpenSSL 1.1 runtime remains in bundle: {stale}")

    report: dict[str, Any] = {
        "python": sys.version,
        "openssl": ssl.OPENSSL_VERSION,
        "sqlite": sqlite3.sqlite_version,
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
        "ffmpeg": {"version": ffmpeg_version, "sha256": sha256(ffmpeg)},
        "ffprobe": {"version": ffprobe_version, "sha256": sha256(ffprobe)},
        "critical_files": {},
    }

    critical = [
        contents / "python310.dll",
        contents / "libssl-3.dll",
        contents / "libcrypto-3.dll",
        contents / "sqlite3.dll",
        contents / "ctranslate2" / "ctranslate2.dll",
        contents / "torch" / "lib" / "torch_cuda.dll",
        contents / "torch" / "lib" / "cublas64_12.dll",
        contents / "torch" / "lib" / "cublasLt64_12.dll",
        contents / "torch" / "lib" / "cudart64_12.dll",
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
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "python": report["python"],
                "openssl": report["openssl"],
                "sqlite": report["sqlite"],
                "verified_distributions": len(versions),
                "torch_compiled_arch_flags": arch_flags,
                "onnxruntime_providers": providers,
                "patch_level": patch_metadata["patch_level"],
                "ffmpeg": ffmpeg_version,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    _ = handles
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
