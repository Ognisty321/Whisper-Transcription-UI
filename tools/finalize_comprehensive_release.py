#!/usr/bin/env python3
"""Finalize the comprehensive Faster-Whisper-XXL modernization release."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def hash_entry(args: tuple[Path, Path]) -> tuple[str, int, str]:
    root, path = args
    return path.relative_to(root).as_posix(), path.stat().st_size, sha256(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("runtime_report", type=Path)
    parser.add_argument("test_report", type=Path)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--original-url", required=True)
    parser.add_argument("--original-size", type=int, required=True)
    parser.add_argument("--original-sha256", required=True)
    parser.add_argument("--git-sha", required=True)
    args = parser.parse_args()

    bundle = args.bundle_root.resolve()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    if not bundle.is_dir():
        raise NotADirectoryError(bundle)

    runtime = json.loads(args.runtime_report.read_text(encoding="utf-8"))
    tests = json.loads(args.test_report.read_text(encoding="utf-8"))
    executable = bundle / "faster-whisper-xxl.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)

    built_at = datetime.now(timezone.utc).isoformat()
    release_name = "Faster-Whisper-XXL r245.4 Modernized 2 / RTX 50 / Windows x64"

    readme = """Faster-Whisper-XXL r245.4 — Modernized 2 / RTX 50 / Windows x64
============================================================================

To jest pełna, przenośna paczka programu. Rozpakuj cały katalog i nie przenoś
samego pliku EXE poza folder, ponieważ biblioteki znajdują się w _xxl_data.

Najważniejsze zmiany
--------------------
- CPython 3.10.21 zamiast 3.10.11, z zachowaniem zgodności bytecode'u 3.10.
- OpenSSL 3.5.7 zamiast niewspieranego OpenSSL 1.1.1t.
- SQLite 3.53.4.
- PyInstaller 6.22.1 dla przebudowanego launchera.
- PyTorch 2.11.0 + CUDA 12.8, torchvision/torchaudio 0.26/2.11.
- CTranslate2 4.8.1 z poprawką INT8 dla NVIDIA Blackwell/RTX 50.
- ONNX Runtime GPU 1.23.2.
- FFmpeg i ffprobe 9.0.
- PyAV 17.1, tokenizers 0.23.1 i huggingface-hub 1.28.0.
- Aktualny, spójny stos NumPy/SciPy/pandas/librosa/scikit-learn.
- pyannote.audio 3.4.0: najnowsza linia zachowująca API 3.x używane przez XXL.
- Silero VAD v6 oraz bezpieczne poprawki przeniesione z faster-whisper 1.2.1.
- Naprawa błędu r245.4 dla jednoczesnych opcji --diarize i --postfix.
- Aktualizacja bibliotek auditok, WebRTC VAD, MDX/RoFormer i warstwy sieciowej.

Dlaczego nie zastąpiono całego faster_whisper wersją upstream
-------------------------------------------------------------
Kod Faster-Whisper-XXL jest mocno zmodyfikowanym forkiem 1.1.1. Zawiera
niestandardowe VAD-y, MDX/RoFormer, diarization, writerów i opcje CLI, których
nie ma upstream. Pełna zamiana katalogu usunęłaby te funkcje. Zamiast tego
zachowano kod XXL i przeniesiono sprawdzone, kompatybilne poprawki: Silero VAD
v6, obsługę <|nocaptions|>, poprawkę granic timestampów, nowy mechanizm
pobierania modeli i obsługę distil-large-v3.5.

Uruchomienie
------------
  faster-whisper-xxl.exe plik.wav --device cuda --compute_type auto

Diagnostyka wersji i środowiska:
  faster-whisper-xxl.exe --runtime-info
  faster-whisper-xxl.exe --checkcuda

Dla diagnostycznego porównania ścieżki INT8 można użyć:
  --compute_type float16

Sterownik NVIDIA
----------------
Użyj aktualnego sterownika NVIDIA zgodnego z CUDA 12.8. Runtime CUDA, cuBLAS i
cuDNN jest dostarczony w paczce; osobny CUDA Toolkit nie jest wymagany.

Integralność
------------
BUILD-INFO.json opisuje build i testy. RUNTIME-VERIFICATION.json zawiera wersje
oraz sumy krytycznych DLL. FILE-MANIFEST-SHA256.txt zawiera sumę każdego pliku.
Launcher został przebudowany i nie ma podpisu autora; SmartScreen może pokazać
ostrzeżenie.

Ograniczenie weryfikacji
------------------------
Automatyczne testy wykonano na Windows Server 2022 x64. Runner nie miał
fizycznej karty NVIDIA, więc rzeczywista transkrypcja na RTX 50 nadal wymaga
testu na komputerze docelowym. Zweryfikowano jednak skompilowane sm_120,
wersję CTranslate2 z poprawką Blackwell INT8, CUDAExecutionProvider oraz
komplet krytycznych bibliotek.
"""

    build_info: dict[str, Any] = {
        "format_version": 2,
        "release": release_name,
        "built_at_utc": built_at,
        "source_revision": args.git_sha,
        "original_archive": {
            "url": args.original_url,
            "size_bytes": args.original_size,
            "sha256": args.original_sha256.upper(),
        },
        "application": {
            "upstream_bundle": "Faster-Whisper-XXL r245.4",
            "custom_faster_whisper_base": runtime.get("faster_whisper_custom_base"),
            "launcher": "PyInstaller 6.22.1 / CPython 3.10.21",
            "executable_sha256": sha256(executable),
            "policy": (
                "Preserve XXL-specific application code; replace coherent native/runtime stacks "
                "and backport compatible upstream fixes instead of deleting custom features."
            ),
        },
        "runtime": {
            "python": runtime.get("python"),
            "openssl": runtime.get("openssl"),
            "sqlite": runtime.get("sqlite"),
            "versions": runtime.get("versions"),
            "torch_cuda_runtime": runtime.get("torch_cuda_runtime"),
            "torch_compiled_arch_flags": runtime.get("torch_compiled_arch_flags"),
            "onnxruntime_providers": runtime.get("onnxruntime_providers"),
            "ffmpeg": runtime.get("ffmpeg"),
            "ffprobe": runtime.get("ffprobe"),
        },
        "fixes": {
            "main_bytecode": runtime.get("main_bytecode_patches"),
            "runtime_backports": runtime.get("patch_metadata"),
        },
        "tests": tests,
        "physical_rtx_50_tested": False,
    }

    readme_path = bundle / "README_MODERNIZED2_PL.txt"
    build_info_path = bundle / "BUILD-INFO.json"
    runtime_path = bundle / "RUNTIME-VERIFICATION.json"
    test_path = bundle / "TEST-RESULTS.json"
    manifest_path = bundle / "FILE-MANIFEST-SHA256.txt"
    critical_path = bundle / "SHA256SUMS.txt"

    readme_path.write_text(readme, encoding="utf-8")
    build_info_path.write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    runtime_path.write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    test_path.write_text(
        json.dumps(tests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    files = sorted(
        path
        for path in bundle.rglob("*")
        if path.is_file() and path not in {manifest_path, critical_path}
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        hashed = list(executor.map(hash_entry, ((bundle, path) for path in files)))
    hashed.sort(key=lambda item: item[0].lower())
    manifest_path.write_text(
        "\n".join(f"{digest} *{relative}" for relative, _, digest in hashed) + "\n",
        encoding="utf-8",
    )

    critical_files = [
        executable,
        readme_path,
        build_info_path,
        runtime_path,
        test_path,
        manifest_path,
        bundle / "ffmpeg.exe",
        bundle / "ffprobe.exe",
        bundle / "_xxl_data" / "python310.dll",
        bundle / "_xxl_data" / "libssl-3.dll",
        bundle / "_xxl_data" / "libcrypto-3.dll",
        bundle / "_xxl_data" / "sqlite3.dll",
        bundle / "_xxl_data" / "ctranslate2" / "ctranslate2.dll",
        bundle / "_xxl_data" / "torch" / "lib" / "torch_cuda.dll",
        bundle / "_xxl_data" / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll",
    ]
    missing = [str(path) for path in critical_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Critical release files are missing: {missing}")
    critical_path.write_text(
        "\n".join(
            f"{sha256(path)} *{path.relative_to(bundle).as_posix()}"
            for path in critical_files
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "release": release_name,
        "built_at_utc": built_at,
        "source_revision": args.git_sha,
        "executable_sha256": sha256(executable),
        "file_count_before_manifest": len(files),
        "uncompressed_bytes_before_manifests": sum(size for _, size, _ in hashed),
        "manifest_sha256": sha256(manifest_path),
        "critical_checksums_sha256": sha256(critical_path),
        "physical_rtx_50_tested": False,
    }
    (report_dir / "release-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for path in [readme_path, build_info_path, runtime_path, test_path, manifest_path, critical_path]:
        (report_dir / path.name).write_bytes(path.read_bytes())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
