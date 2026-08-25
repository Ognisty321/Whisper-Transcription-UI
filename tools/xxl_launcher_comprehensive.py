#!/usr/bin/env python3
"""Hardened launcher for the externalized Faster-Whisper-XXL r245.4 code."""

from __future__ import annotations

import json
import marshal
import os
import platform
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, NamedTuple

_DLL_HANDLES: list[Any] = []


def _contents_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()


def _configure_environment(contents: Path) -> list[str]:
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("NUMBA_CACHE_DIR", str(contents / "numba_cache"))

    # Put the coherent CUDA 12.8 runtime before all other bundle locations.
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
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join(existing + ([old_path] if old_path else []))
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        for path in existing:
            try:
                _DLL_HANDLES.append(os.add_dll_directory(path))
            except OSError:
                pass

    text = str(contents)
    sys.path[:] = [item for item in sys.path if os.path.abspath(item or os.curdir) != os.path.abspath(text)]
    sys.path.insert(0, text)

    # Ensure HTTPS model downloads use the refreshed bundled CA store.
    try:
        import certifi
        ca_file = certifi.where()
        if ca_file and Path(ca_file).is_file():
            os.environ.setdefault("SSL_CERT_FILE", ca_file)
            os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_file)
    except Exception:
        pass
    return existing


def _install_torchaudio_compat() -> dict[str, Any]:
    """Restore only the legacy TorchAudio I/O surface needed by Pyannote 3.x.

    TorchAudio 2.9+ removed media I/O in favor of TorchCodec. The abandoned XXL
    bundle contains Pyannote 3.x code that evaluates ``torchaudio.AudioMetaData``
    during import and may call ``info/load/save/list_audio_backends``. These
    wrappers use the already bundled SoundFile implementation and leave all
    TorchAudio transforms/models untouched.
    """

    import re
    import torchaudio

    class AudioMetaData(NamedTuple):
        sample_rate: int
        num_frames: int
        num_channels: int
        bits_per_sample: int
        encoding: str

    def _metadata(uri: Any, *args: Any, **kwargs: Any) -> AudioMetaData:
        import soundfile as sf
        info = sf.info(uri)
        subtype = str(getattr(info, "subtype", "") or "")
        match = re.search(r"(\d+)", subtype)
        bits = int(match.group(1)) if match else 0
        if subtype.startswith("PCM_U"):
            encoding = "PCM_U"
        elif subtype.startswith("PCM_F") or subtype in {"FLOAT", "DOUBLE"}:
            encoding = "PCM_F"
        elif subtype.startswith("PCM"):
            encoding = "PCM_S"
        elif subtype in {"ULAW", "ALAW", "VORBIS", "OPUS"}:
            encoding = subtype
        else:
            encoding = str(getattr(info, "format", "UNKNOWN") or "UNKNOWN")
        return AudioMetaData(
            sample_rate=int(info.samplerate),
            num_frames=int(info.frames),
            num_channels=int(info.channels),
            bits_per_sample=bits,
            encoding=encoding,
        )

    def _load(
        uri: Any,
        frame_offset: int = 0,
        num_frames: int = -1,
        normalize: bool = True,
        channels_first: bool = True,
        format: str | None = None,
        buffer_size: int = 4096,
        backend: str | None = None,
        **kwargs: Any,
    ) -> tuple[Any, int]:
        del normalize, format, buffer_size, backend, kwargs
        import soundfile as sf
        import torch
        frames = -1 if num_frames is None or int(num_frames) < 0 else int(num_frames)
        data, sample_rate = sf.read(
            uri,
            start=max(0, int(frame_offset)),
            frames=frames,
            dtype="float32",
            always_2d=True,
        )
        if channels_first:
            data = data.T
        return torch.from_numpy(data.copy()), int(sample_rate)

    def _save(
        uri: Any,
        src: Any,
        sample_rate: int,
        channels_first: bool = True,
        compression: Any = None,
        format: str | None = None,
        encoding: str | None = None,
        bits_per_sample: int | None = None,
        buffer_size: int = 4096,
        backend: str | None = None,
        **kwargs: Any,
    ) -> None:
        del compression, format, encoding, bits_per_sample, buffer_size, backend, kwargs
        import soundfile as sf
        data = src.detach().cpu().numpy() if hasattr(src, "detach") else src
        if channels_first and getattr(data, "ndim", 0) == 2:
            data = data.T
        sf.write(uri, data, int(sample_rate))

    added: list[str] = []
    # AudioMetaData is a type annotation in Pyannote 3.x; always expose the
    # compatibility definition under both historical import locations.
    torchaudio.AudioMetaData = AudioMetaData  # type: ignore[attr-defined]
    added.append("AudioMetaData")

    backend_module = sys.modules.get("torchaudio.backend")
    if backend_module is None:
        backend_module = types.ModuleType("torchaudio.backend")
        backend_module.__path__ = []  # type: ignore[attr-defined]
        sys.modules["torchaudio.backend"] = backend_module
        torchaudio.backend = backend_module  # type: ignore[attr-defined]
    common_module = sys.modules.get("torchaudio.backend.common")
    if common_module is None:
        common_module = types.ModuleType("torchaudio.backend.common")
        sys.modules["torchaudio.backend.common"] = common_module
        backend_module.common = common_module  # type: ignore[attr-defined]
    common_module.AudioMetaData = AudioMetaData  # type: ignore[attr-defined]

    compatibility = {
        "list_audio_backends": lambda: ["soundfile"],
        "get_audio_backend": lambda: "soundfile",
        "set_audio_backend": lambda backend=None: None,
        "info": _metadata,
        "load": _load,
        "save": _save,
    }
    for name, value in compatibility.items():
        if not hasattr(torchaudio, name):
            setattr(torchaudio, name, value)
            added.append(name)

    return {
        "torchaudio_version": str(getattr(torchaudio, "__version__", "unknown")),
        "compatibility_members_added": added,
        "io_backend": "soundfile",
    }


def _module_version(name: str, import_name: str | None = None) -> dict[str, Any]:
    import importlib
    result: dict[str, Any] = {"distribution": name, "module": import_name or name}
    try:
        module = importlib.import_module(import_name or name)
        result["version"] = str(getattr(module, "__version__", "unknown"))
        result["file"] = str(getattr(module, "__file__", ""))
        result["ok"] = True
    except Exception as exc:
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _runtime_report(contents: Path, dll_dirs: list[str], deep: bool, torchaudio_compat: dict[str, Any]) -> dict[str, Any]:
    modules = [
        ("torch", "torch"),
        ("torchvision", "torchvision"),
        ("torchaudio", "torchaudio"),
        ("ctranslate2", "ctranslate2"),
        ("onnxruntime-gpu", "onnxruntime"),
        ("faster-whisper-custom", "faster_whisper"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("scikit-learn", "sklearn"),
        ("pandas", "pandas"),
        ("librosa", "librosa"),
        ("numba", "numba"),
        ("av", "av"),
        ("huggingface-hub", "huggingface_hub"),
        ("tokenizers", "tokenizers"),
        ("requests", "requests"),
        ("certifi", "certifi"),
        ("pyannote.audio", "pyannote.audio"),
    ]
    report: dict[str, Any] = {
        "release": "Faster-Whisper-XXL r245.4 comprehensive modernization",
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "contents": str(contents),
        "dll_search_dirs": dll_dirs,
        "torchaudio_compatibility": torchaudio_compat,
        "modules": [_module_version(name, module) for name, module in modules],
    }
    try:
        import ssl
        report["openssl"] = ssl.OPENSSL_VERSION
        report["default_verify_paths"] = ssl.get_default_verify_paths()._asdict()
    except Exception as exc:
        report["ssl_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import torch
        report["torch_cuda_runtime"] = torch.version.cuda
        report["torch_cuda_available"] = torch.cuda.is_available()
        report["torch_arch_flags"] = torch._C._cuda_getArchFlags()  # type: ignore[attr-defined]
        report["cudnn_version"] = torch.backends.cudnn.version()
    except Exception as exc:
        report["torch_probe_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import onnxruntime
        report["onnxruntime_providers"] = onnxruntime.get_available_providers()
    except Exception as exc:
        report["onnxruntime_probe_error"] = f"{type(exc).__name__}: {exc}"
    try:
        ffmpeg = Path(sys.executable).resolve().parent / "ffmpeg.exe"
        if ffmpeg.is_file():
            proc = subprocess.run([str(ffmpeg), "-version"], capture_output=True, text=True, timeout=20)
            report["ffmpeg"] = proc.stdout.splitlines()[0] if proc.stdout else f"exit {proc.returncode}"
    except Exception as exc:
        report["ffmpeg_probe_error"] = f"{type(exc).__name__}: {exc}"

    if deep:
        try:
            import numpy as np
            a = np.arange(12, dtype=np.float32).reshape(3, 4)
            report["numpy_self_test"] = float((a @ a.T).sum())
        except Exception as exc:
            report["numpy_self_test_error"] = f"{type(exc).__name__}: {exc}"
        try:
            import ctranslate2
            report["ctranslate2_cuda_devices"] = ctranslate2.get_cuda_device_count()
            report["ctranslate2_cpu_types"] = sorted(ctranslate2.get_supported_compute_types("cpu"))
        except Exception as exc:
            report["ctranslate2_self_test_error"] = f"{type(exc).__name__}: {exc}"
    return report


def _load_code(path: Path) -> types.CodeType:
    value = marshal.loads(path.read_bytes())
    if not isinstance(value, types.CodeType):
        raise TypeError(f"{path} does not contain a Python code object")
    return value


def _execute_original(contents: Path) -> None:
    scripts = contents / "xxl_original_scripts"
    manifest_path = contents / "xxl_externalization_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing reconstruction manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    order = manifest.get("script_order")
    if not isinstance(order, list) or "__main__" not in order:
        raise RuntimeError("Invalid reconstruction manifest")

    namespace = globals()
    namespace["__name__"] = "__main__"
    namespace["__package__"] = None
    namespace["__cached__"] = None
    for name in order:
        path = scripts / f"{name}.marshal"
        if not path.is_file():
            raise FileNotFoundError(f"Missing original script bytecode: {path}")
        namespace["__file__"] = str(contents / f"{name}.py")
        exec(_load_code(path), namespace, namespace)


def main() -> None:
    contents = _contents_dir()
    dll_dirs = _configure_environment(contents)
    torchaudio_compat = _install_torchaudio_compat()
    if "--xxl-runtime-info" in sys.argv or "--xxl-self-test" in sys.argv:
        deep = "--xxl-self-test" in sys.argv
        report = _runtime_report(contents, dll_dirs, deep=deep, torchaudio_compat=torchaudio_compat)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        failures = [item for item in report["modules"] if not item.get("ok")]
        if failures or "ssl_error" in report or "torch_probe_error" in report:
            raise SystemExit(2)
        raise SystemExit(0)
    _execute_original(contents)


if __name__ == "__main__":
    main()
