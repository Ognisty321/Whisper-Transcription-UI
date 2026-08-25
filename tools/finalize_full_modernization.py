#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def scan_dist_info(contents: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for di in sorted(contents.glob("*.dist-info"), key=lambda p: p.name.lower()):
        metadata = di / "METADATA"
        name = version = None
        if metadata.is_file():
            for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Name:") and not name:
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("Version:") and not version:
                    version = line.split(":", 1)[1].strip()
                if name and version:
                    break
        if name and version:
            result[name] = version
    return dict(sorted(result.items(), key=lambda kv: kv[0].lower()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("report", type=Path)
    ap.add_argument("--git-sha", required=True)
    args = ap.parse_args()
    bundle = args.bundle.resolve()
    report = args.report.resolve()
    contents = bundle / "_xxl_data"
    if not bundle.is_dir() or not contents.is_dir():
        raise NotADirectoryError(bundle)

    runtime_path = report / "packaged-runtime-info.json"
    stage_path = report / "stage-apply.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.is_file() else {}
    stage = json.loads(stage_path.read_text(encoding="utf-8")) if stage_path.is_file() else {}
    packages = scan_dist_info(contents)

    expected = {
        "torch": "2.11.0+cu128",
        "torchvision": "0.26.0+cu128",
        "torchaudio": "2.11.0+cu128",
        "ctranslate2": "4.8.1",
        "onnxruntime-gpu": "1.23.2",
        "numpy": "2.2.6",
        "scipy": "1.15.3",
        "scikit-learn": "1.7.2",
        "pandas": "2.3.3",
        "numba": "0.67.0",
        "llvmlite": "0.49.0",
        "pyannote.audio": "3.4.0",
        "lightning": "2.6.5",
        "pytorch-lightning": "2.6.5",
        "torchmetrics": "1.9.0",
        "huggingface-hub": "1.28.0",
        "tokenizers": "0.23.1",
        "sentencepiece": "0.2.2",
        "av": "17.1.0",
        "librosa": "0.11.0",
        "soundfile": "0.14.0",
        "soxr": "1.1.0",
        "auditok": "0.2.0",
    }
    lower = {k.lower(): v for k, v in packages.items()}
    mismatches = {}
    for name, wanted in expected.items():
        actual = lower.get(name.lower())
        if actual != wanted:
            mismatches[name] = {"expected": wanted, "actual": actual}
    if mismatches:
        raise RuntimeError(f"Final package version mismatch: {mismatches}")

    if not str(runtime.get("python", "")).startswith("3.10.21"):
        raise RuntimeError(f"Final packaged Python is not 3.10.21: {runtime.get('python')!r}")
    if runtime.get("python_magic") != "6f0d0d0a":
        raise RuntimeError("Final CPython bytecode magic mismatch")
    if "OpenSSL 1.1.1w" not in str(runtime.get("openssl", "")):
        raise RuntimeError(f"Final OpenSSL is not 1.1.1w: {runtime.get('openssl')!r}")
    if "sm_120" not in str(runtime.get("torch_arch_flags", "")):
        raise RuntimeError("Final Torch runtime does not report sm_120")
    if "CUDAExecutionProvider" not in runtime.get("onnxruntime_providers", []):
        raise RuntimeError("Final ONNX Runtime does not expose CUDAExecutionProvider")

    ffmpeg_text = (report / "ffmpeg-version.txt").read_text(encoding="utf-8", errors="replace")
    first_ffmpeg_line = next((line.strip() for line in ffmpeg_text.splitlines() if line.strip()), "")
    if not re.search(r"ffmpeg version n?9\.0", ffmpeg_text, re.I):
        raise RuntimeError("Final FFmpeg is not 9.0")

    holds = [
        {
            "component": "faster-whisper application code",
            "version": "XXL custom 1.1.1 / r245.4 codebase",
            "reason": "Upstream 1.2.x does not contain Purfview's XXL VAD/MDX/diarization/writer/CLI extensions; replacing it would remove functionality.",
        },
        {
            "component": "auditok",
            "version": "0.2.0",
            "reason": "Auditok 0.5.2 removed private AudioRegion._meta used by custom XXL vad5_auditok.py; integration test proved the regression.",
        },
        {
            "component": "pyannote ecosystem",
            "version": "pyannote.audio 3.4.0 with core 5.0/database 5.1/metrics 3.2.1/pipeline 3.0.1",
            "reason": "XXL custom code targets pyannote 3.x. Later major ecosystem versions are API-incompatible. A narrow TorchAudio I/O compatibility backport is applied instead.",
        },
        {
            "component": "PyTorch CUDA line",
            "version": "2.11.0 + cu128",
            "reason": "Newest coherent official Windows CPython 3.10 CUDA 12.8 set used here; newer general Torch releases move to a different CUDA line and are not a drop-in CTranslate2/XXL upgrade.",
        },
        {
            "component": "onnxruntime-gpu",
            "version": "1.23.2",
            "reason": "Newest compatible Windows CPython 3.10 GPU wheel used by this reconstruction; later release lines do not provide the required cp310 Windows wheel.",
        },
    ]

    compatibility_patches = stage.get("compatibility_patches", {})
    build_info = {
        "format_version": 2,
        "release": "Faster-Whisper-XXL r245.4 Full Modernization / RTX 50",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": args.git_sha,
        "platform": "Windows x64",
        "application": {
            "upstream_bundle": "Purfview Faster-Whisper-XXL r245.4",
            "custom_application_code_preserved": True,
            "pyinstaller_reconstruction": "6.22.2",
        },
        "runtime": runtime,
        "ffmpeg": first_ffmpeg_line,
        "packages": packages,
        "intentional_holds": holds,
        "compatibility_patches": compatibility_patches,
        "test_scope": {
            "windows_runner": "Windows Server 2022 x64",
            "cli_help_version_checkcuda": True,
            "cpu_end_to_end_transcription": True,
            "vad_silero_v5": True,
            "vad_webrtc": True,
            "vad_auditok": True,
            "vad_pyannote_onnx_v3": True,
            "vad_pyannote_v3": True,
            "mdx_kim2": True,
            "physical_rtx_50_gpu": False,
            "note": "No physical NVIDIA GPU was available in CI; RTX 50 support is verified from sm_120-capable binaries, CTranslate2 4.8.1, CUDA 12.8 DLLs and provider loading.",
        },
    }

    readme = """Faster-Whisper-XXL r245.4 — FULL MODERNIZATION / RTX 50
============================================================

To jest kompletna przebudowana paczka Windows, a nie patch.

Najważniejsze zmiany:
- CPython 3.10.21 zbudowany ze źródeł dla Windows x64, ten sam magic bytecode co oryginalny XXL
- PyInstaller 6.22.2
- PyTorch 2.11.0 + CUDA 12.8, torchvision 0.26.0, torchaudio 2.11.0
- CTranslate2 4.8.1 z poprawką INT8/Blackwell RTX 50
- ONNX Runtime GPU 1.23.2
- FFmpeg 9.0
- szeroka aktualizacja NumPy/SciPy/scikit-learn/Pandas/Numba, Hugging Face, audio, Lightning i bibliotek pomocniczych
- pyannote.audio 3.4.0 pozostawione w zgodnej linii 3.x i zaadaptowane do nowego TorchAudio przez wąski shim I/O oparty na SoundFile
- Auditok celowo 0.2.0: nowsze 0.5.2 łamie prywatne API używane przez XXL

Nie podmieniono customowego kodu Faster-Whisper-XXL na upstream Faster-Whisper 1.2.x,
ponieważ usunęłoby to funkcje XXL (niestandardowe VAD, MDX, diarization, writery i CLI).

Testy Windows obejmują CLI, pełną transkrypcję CPU, Silero v5, WebRTC, Auditok,
pyannote ONNX, pyannote Torch oraz MDX Kim2. Końcowy ZIP jest dodatkowo testowany przez 7-Zip.

Nie było fizycznej karty RTX 50 w CI. Pakiet zawiera jednak sm_120, CUDA 12.8 i
CTranslate2 4.8.1 z poprawką Blackwell/INT8. Rzeczywisty test wydajności GPU trzeba
wykonać na docelowym komputerze.

Nie przenoś samego EXE. Rozpakuj i zachowaj cały katalog Faster-Whisper-XXL.
"""

    readme_path = bundle / "README_FULL_MODERNIZATION_PL.txt"
    info_path = bundle / "FULL-MODERNIZATION-INFO.json"
    readme_path.write_text(readme, encoding="utf-8")
    info_path.write_text(json.dumps(build_info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    critical = [
        bundle / "faster-whisper-xxl.exe",
        bundle / "ffmpeg.exe",
        contents / "python310.dll",
        contents / "libssl-1_1.dll",
        contents / "libcrypto-1_1.dll",
        contents / "ctranslate2" / "ctranslate2.dll",
        contents / "torch" / "lib" / "torch_cuda.dll",
        contents / "torch" / "lib" / "cublas64_12.dll",
        contents / "torch" / "lib" / "cublasLt64_12.dll",
        contents / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll",
        readme_path,
        info_path,
    ]
    missing = [str(p) for p in critical if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing final critical files: {missing}")
    checksum_lines = [f"{sha256(p)} *{p.relative_to(bundle).as_posix()}" for p in critical]
    sums_path = bundle / "SHA256SUMS_MODERNIZED.txt"
    sums_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    summary = {
        "success": True,
        "release": build_info["release"],
        "python": runtime.get("python"),
        "openssl": runtime.get("openssl"),
        "torch": runtime.get("torch"),
        "torch_cuda": runtime.get("torch_cuda"),
        "torch_arch_flags": runtime.get("torch_arch_flags"),
        "ctranslate2": runtime.get("ctranslate2"),
        "onnxruntime": runtime.get("onnxruntime"),
        "ffmpeg": first_ffmpeg_line,
        "package_count": len(packages),
        "intentional_hold_count": len(holds),
        "critical_checksums": {p.relative_to(bundle).as_posix(): sha256(p) for p in critical},
    }
    (report / "final-modernization-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
