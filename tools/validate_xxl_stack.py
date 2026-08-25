#!/usr/bin/env python3
"""Deep compatibility checks for a modernized Faster-Whisper-XXL bundle."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import inspect
import json
import math
import os
import ssl
import subprocess
import sys
import tempfile
import traceback
import wave
from pathlib import Path
from typing import Any, Callable


def configure(contents: Path) -> list[str]:
    candidates = [
        contents / "torch" / "lib",
        contents / "ctranslate2",
        contents / "onnxruntime" / "capi",
        contents / "av.libs",
        contents / "numpy.libs",
        contents / "scipy.libs",
        contents / "sklearn.libs",
        contents / "pandas.libs",
        contents,
    ]
    existing = [str(path) for path in candidates if path.is_dir()]
    os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])
    handles = []
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        for path in existing:
            try:
                handles.append(os.add_dll_directory(path))
            except OSError:
                pass
    sys.path.insert(0, str(contents))
    globals()["_DLL_HANDLES"] = handles
    return existing


def module_version(module: Any, distribution: str) -> str:
    value = getattr(module, "__version__", None)
    if value is not None:
        return str(value)
    try:
        return importlib.metadata.version(distribution)
    except Exception:
        return "unknown"


def ensure_inside(module: Any, root: Path, name: str) -> str:
    raw = getattr(module, "__file__", None)
    if not raw:
        raise RuntimeError(f"{name} has no __file__")
    path = Path(raw).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"{name} loaded outside bundle: {path}") from exc
    return str(path)


def write_wav(path: Path, seconds: float = 0.35, rate: int = 16000) -> None:
    samples = [int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(int(rate * seconds))]
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        import struct
        stream.writeframes(b"".join(struct.pack("<h", value) for value in samples))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contents_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect", action="append", default=[], help="distribution=version-prefix")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--deep", action="store_true")
    args = parser.parse_args()

    contents = args.contents_dir.resolve()
    if not contents.is_dir():
        raise NotADirectoryError(contents)
    dll_dirs = configure(contents)
    expected = dict(item.split("=", 1) for item in args.expect)
    report: dict[str, Any] = {
        "python": sys.version,
        "contents": str(contents),
        "dll_search_dirs": dll_dirs,
        "openssl": ssl.OPENSSL_VERSION,
        "checks": [],
        "versions": {},
        "module_files": {},
        "failures": [],
    }

    def check(name: str, fn: Callable[[], Any]) -> None:
        try:
            value = fn()
            report["checks"].append({"name": name, "ok": True, "value": value})
        except BaseException as exc:
            report["checks"].append({
                "name": name,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=15),
            })
            report["failures"].append(name)

    imports = [
        ("torch", "torch"),
        ("torchvision", "torchvision"),
        ("torchaudio", "torchaudio"),
        ("ctranslate2", "ctranslate2"),
        ("onnxruntime-gpu", "onnxruntime"),
        ("faster-whisper", "faster_whisper"),
        ("tokenizers", "tokenizers"),
        ("huggingface-hub", "huggingface_hub"),
        ("requests", "requests"),
        ("urllib3", "urllib3"),
        ("certifi", "certifi"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("scikit-learn", "sklearn"),
        ("pandas", "pandas"),
        ("librosa", "librosa"),
        ("numba", "numba"),
        ("llvmlite", "llvmlite"),
        ("soundfile", "soundfile"),
        ("soxr", "soxr"),
        ("av", "av"),
        ("psutil", "psutil"),
        ("Pillow", "PIL"),
        ("matplotlib", "matplotlib"),
        ("pyannote.audio", "pyannote.audio"),
        ("pyannote.core", "pyannote.core"),
        ("lightning", "lightning"),
        ("torchmetrics", "torchmetrics"),
        ("optuna", "optuna"),
        ("SQLAlchemy", "sqlalchemy"),
    ]
    modules: dict[str, Any] = {}
    for distribution, import_name in imports:
        def do_import(distribution: str = distribution, import_name: str = import_name) -> dict[str, str]:
            module = importlib.import_module(import_name)
            modules[import_name] = module
            version = module_version(module, distribution)
            report["versions"][distribution] = version
            report["module_files"][distribution] = ensure_inside(module, contents, distribution)
            prefix = expected.get(distribution)
            if prefix and not version.startswith(prefix):
                raise RuntimeError(f"{distribution}={version!r}, expected prefix {prefix!r}")
            return {"version": version, "file": report["module_files"][distribution]}
        check(f"import:{distribution}", do_import)

    def custom_faster_whisper() -> dict[str, Any]:
        fw = modules["faster_whisper"]
        diar = importlib.import_module("faster_whisper.diarization")
        utils = importlib.import_module("faster_whisper.utils")
        missing = [name for name in ("download_model_other", "get_writer_alt") if not hasattr(utils, name)]
        if missing:
            raise RuntimeError(f"missing XXL custom utils: {missing}")
        transcribe = importlib.import_module("faster_whisper.transcribe")
        signature = str(inspect.signature(fw.WhisperModel.transcribe))
        if not hasattr(transcribe, "BatchedInferencePipeline") and not hasattr(fw, "BatchedInferencePipeline"):
            raise RuntimeError("BatchedInferencePipeline is missing")
        return {"diarization": str(diar.__file__), "signature": signature[:4000]}
    check("faster-whisper-custom-api", custom_faster_whisper)

    def gpu_runtime() -> dict[str, Any]:
        torch = modules["torch"]
        ct2 = modules["ctranslate2"]
        ort = modules["onnxruntime"]
        flags = torch._C._cuda_getArchFlags()  # type: ignore[attr-defined]
        if "sm_120" not in flags.split():
            raise RuntimeError(f"sm_120 missing from {flags!r}")
        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" not in providers:
            raise RuntimeError(f"CUDAExecutionProvider missing: {providers}")
        return {
            "torch_cuda": torch.version.cuda,
            "arch_flags": flags,
            "cudnn": torch.backends.cudnn.version(),
            "torch_cuda_available": torch.cuda.is_available(),
            "ctranslate2_cuda_devices": ct2.get_cuda_device_count(),
            "ctranslate2_cpu_types": sorted(ct2.get_supported_compute_types("cpu")),
            "onnxruntime_providers": providers,
        }
    check("gpu-runtime", gpu_runtime)

    def dll_inventory() -> dict[str, list[str]]:
        names = ["cublas64_12.dll", "cublasLt64_12.dll", "cudart64_12.dll", "cudnn64_8.dll", "cudnn64_9.dll"]
        found = {name: [str(p.relative_to(contents)) for p in contents.rglob(name)] for name in names}
        stale = [path for path in found["cudnn64_8.dll"] if path.lower().startswith("ctranslate2")]
        if stale:
            raise RuntimeError(f"stale cuDNN 8 next to CTranslate2: {stale}")
        for required in ("cublas64_12.dll", "cublasLt64_12.dll", "cudart64_12.dll"):
            if not found[required]:
                raise RuntimeError(f"missing {required}")
        return found
    check("dll-inventory", dll_inventory)

    if args.deep:
        def numerical() -> dict[str, Any]:
            import numpy as np
            from scipy import signal
            from sklearn.preprocessing import StandardScaler
            import pandas as pd
            import librosa
            import numba
            import soxr
            a = np.arange(12, dtype=np.float32).reshape(3, 4)
            covariance = a @ a.T
            filtered = signal.resample(np.sin(np.linspace(0, 4, 64)), 32)
            scaled = StandardScaler().fit_transform(a)
            frame = pd.DataFrame(a)
            resampled = librosa.resample(np.ones(800, dtype=np.float32), orig_sr=16000, target_sr=8000)
            converted = soxr.resample(np.ones(800, dtype=np.float32), 16000, 8000)
            @numba.njit(cache=False)
            def total(x):
                value = 0.0
                for item in x:
                    value += item
                return value
            compiled = float(total(np.arange(10, dtype=np.float64)))
            return {
                "matmul_sum": float(covariance.sum()),
                "scipy_len": len(filtered),
                "scaled_mean": float(abs(scaled.mean())),
                "pandas_shape": list(frame.shape),
                "librosa_len": len(resampled),
                "soxr_len": len(converted),
                "numba_total": compiled,
            }
        check("numerical-audio-stack", numerical)

        def media() -> dict[str, Any]:
            import av
            import soundfile as sf
            import numpy as np
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                wav_path = root / "tone.wav"
                write_wav(wav_path)
                data, rate = sf.read(wav_path)
                with av.open(str(wav_path)) as container:
                    frames = list(container.decode(audio=0))
                if not frames or len(data) == 0 or rate != 16000:
                    raise RuntimeError("media decode returned no data")
                return {"samples": int(len(data)), "rate": rate, "av_frames": len(frames), "peak": float(np.max(np.abs(data)))}
        check("media-decode", media)

        def plotting() -> int:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "plot.png"
                fig = plt.figure()
                plt.plot([0, 1], [0, 1])
                fig.savefig(output)
                plt.close(fig)
                if output.stat().st_size < 100:
                    raise RuntimeError("matplotlib output too small")
                return output.stat().st_size
        check("matplotlib-render", plotting)

    if args.network:
        def network() -> dict[str, Any]:
            import certifi
            import requests
            from huggingface_hub import hf_hub_download
            ca = Path(certifi.where())
            if not ca.is_file() or ca.stat().st_size < 100000:
                raise RuntimeError(f"invalid CA bundle: {ca}")
            response = requests.get("https://huggingface.co/api/models/Systran/faster-whisper-tiny.en", timeout=30)
            response.raise_for_status()
            with tempfile.TemporaryDirectory() as temp:
                config = hf_hub_download("Systran/faster-whisper-tiny.en", "config.json", cache_dir=temp)
                size = Path(config).stat().st_size
            return {"status": response.status_code, "ca": str(ca), "config_bytes": size}
        check("https-and-huggingface", network)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"failures": report["failures"], "versions": report["versions"]}, ensure_ascii=False, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
