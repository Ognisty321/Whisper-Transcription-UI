#!/usr/bin/env python3
"""Create release notes, build metadata, and checksums inside the rebuilt bundle."""

from __future__ import annotations

import argparse
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


def normalize_relative(path: str) -> str:
    return path.replace("\\", "/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("runtime_report", type=Path)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--original-url", required=True)
    parser.add_argument("--original-size", type=int, required=True)
    parser.add_argument("--original-sha256", required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--inference-output", type=Path, required=True)
    args = parser.parse_args()

    bundle = args.bundle_root.resolve()
    report_dir = args.report_dir.resolve()
    runtime_path = args.runtime_report.resolve()
    inference_output = args.inference_output.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    if not bundle.is_dir():
        raise NotADirectoryError(bundle)
    executable = bundle / "faster-whisper-xxl.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if not runtime_path.is_file():
        raise FileNotFoundError(runtime_path)
    if not inference_output.is_file() or inference_output.stat().st_size == 0:
        raise RuntimeError(f"CPU inference output is missing or empty: {inference_output}")

    runtime: dict[str, Any] = json.loads(runtime_path.read_text(encoding="utf-8"))
    versions = runtime.get("versions", {})
    expected = {
        "torch": "2.11.0+cu128",
        "torch_cuda": "12.8",
        "torchvision": "0.26.0+cu128",
        "torchaudio": "2.11.0+cu128",
        "ctranslate2": "4.8.1",
        "onnxruntime_gpu": "1.23.2",
    }
    for name, expected_value in expected.items():
        if versions.get(name) != expected_value:
            raise RuntimeError(f"Unexpected {name}: {versions.get(name)!r}; expected {expected_value!r}")
    if runtime.get("torch_blackwell_sm120_present") is not True:
        raise RuntimeError("Blackwell sm_120 confirmation is missing")
    if runtime.get("onnxruntime_cuda_provider_present") is not True:
        raise RuntimeError("ONNX Runtime CUDA provider confirmation is missing")

    built_at = datetime.now(timezone.utc).isoformat()
    exe_hash = sha256(executable)
    critical_files = runtime.get("critical_files", {})
    if not isinstance(critical_files, dict) or not critical_files:
        raise RuntimeError("Critical runtime file manifest is missing")

    package_runtime = {
        "versions": versions,
        "torch_compiled_arch_flags": runtime.get("torch_compiled_arch_flags"),
        "torch_blackwell_sm120_present": runtime.get("torch_blackwell_sm120_present"),
        "torch_cudnn_version": runtime.get("torch_cudnn_version"),
        "onnxruntime_available_providers": runtime.get("onnxruntime_available_providers"),
        "onnxruntime_cuda_provider_present": runtime.get("onnxruntime_cuda_provider_present"),
        "critical_files": {
            normalize_relative(path): details for path, details in critical_files.items()
        },
    }

    build_info = {
        "format_version": 1,
        "release": "Faster-Whisper-XXL r245.4 RTX50 CUDA 12.8",
        "built_at_utc": built_at,
        "source_revision": args.git_sha,
        "original_archive": {
            "url": args.original_url,
            "size_bytes": args.original_size,
            "sha256": args.original_sha256.upper(),
        },
        "application": {
            "upstream_bundle": "Faster-Whisper-XXL r245.4",
            "reported_cli_version": "1.1.1",
            "launcher": "reconstructed with PyInstaller 6.12.0 and CPython 3.10.11",
            "executable_sha256": exe_hash,
            "code_policy": (
                "Original XXL application modules were preserved as CPython 3.10 bytecode. "
                "The coherent GPU/ML runtime stack was replaced; unrelated application libraries "
                "were not blindly upgraded because that would risk breaking the abandoned custom XXL code."
            ),
        },
        "gpu_runtime": package_runtime,
        "tests": {
            "package_imports_from_bundle": True,
            "critical_dll_presence_and_hashes": True,
            "cli_help_exit_0": True,
            "cli_version_exit_0": True,
            "cli_checkcuda_exit_0": True,
            "cpu_tiny_en_end_to_end_inference_exit_0": True,
            "physical_rtx_50_gpu_tested": False,
            "ci_gpu_note": (
                "The Windows GitHub-hosted runner had no NVIDIA GPU. Blackwell support was verified "
                "from the packaged sm_120 PyTorch architecture, the CTranslate2 version containing "
                "the RTX 50 INT8 fix, successful native imports, and the CUDA provider manifest."
            ),
        },
    }

    readme = """Faster-Whisper-XXL r245.4 — wydanie RTX 50 / CUDA 12.8
================================================================

Co zmieniono
------------
Ta paczka zachowuje autorski kod i funkcje Faster-Whisper-XXL r245.4, ale
rekonstruuje launcher PyInstallera i wymienia spójny stos GPU/ML:

- PyTorch 2.11.0 + CUDA 12.8
- torchvision 0.26.0 + CUDA 12.8
- torchaudio 2.11.0 + CUDA 12.8
- CTranslate2 4.8.1
- ONNX Runtime GPU 1.23.2
- cuDNN 9 dostarczony przez pakiet PyTorch
- obsługa architektury NVIDIA Blackwell sm_120 w skompilowanym PyTorch

CTranslate2 4.8.1 zawiera poprawki dla kart RTX 50, w tym naprawę ścieżki
INT8 używanej przy automatycznym wyborze typu obliczeń.

Instalacja i uruchomienie
-------------------------
1. Rozpakuj CAŁY katalog Faster-Whisper-XXL z ZIP-a.
2. Nie przenoś samego pliku EXE poza katalog — biblioteki są w _xxl_data.
3. Uruchom faster-whisper-xxl.exe tak samo jak w oryginalnym wydaniu.
4. Użyj aktualnego sterownika NVIDIA obsługującego CUDA 12.8.

Przykładowy tryb GPU:
  faster-whisper-xxl.exe plik.wav --device cuda --compute_type auto

CTranslate2 4.8.1 naprawia problem automatycznego INT8 na RTX 50. Gdyby
konkretny sterownik nadal sprawiał problem, diagnostycznym obejściem jest:
  --compute_type float16

Zakres aktualizacji
-------------------
Nie wykonano ślepego podniesienia każdego niezwiązanego pakietu. Autorskie
moduły XXL są porzucone i zależą od konkretnego zachowania bibliotek. Zostały
zachowane, natomiast kompletnie i spójnie wymieniono warstwę odpowiedzialną za
CUDA, Blackwell, transkrypcję, Torch i ONNX Runtime. To minimalizuje ryzyko
uszkodzenia diarization, MDX, writerów i niestandardowych opcji XXL.

Testy
-----
- import nowych torch/torchvision/torchaudio/CTranslate2/ONNX Runtime z paczki
- kontrola wersji i sum krytycznych DLL
- potwierdzenie sm_120 oraz CUDAExecutionProvider
- faster-whisper-xxl.exe --help, --version i --checkcuda: kod wyjścia 0
- pełna transkrypcja testowego WAV na CPU z modelem tiny.en: kod wyjścia 0
- test integralności końcowego ZIP-a

Ograniczenie testu
------------------
Środowisko budowania nie miało fizycznej karty NVIDIA. Nie wykonano więc
pomiaru ani transkrypcji bezpośrednio na RTX 50. Obecność sm_120, wersja
CTranslate2 z poprawką Blackwell/INT8, CUDA 12.8, cuDNN 9 i poprawne ładowanie
DLL zostały zweryfikowane automatycznie.

Bezpieczeństwo i integralność
-----------------------------
Launcher został przebudowany i nie jest podpisany cyfrowo; Windows SmartScreen
może wyświetlić ostrzeżenie. Zweryfikuj sumę SHA-256 ZIP-a podaną obok linku do
pobrania. W katalogu znajdują się również BUILD-INFO.json i SHA256SUMS.txt.
"""

    readme_path = bundle / "README_RTX50_PL.txt"
    build_info_path = bundle / "BUILD-INFO.json"
    runtime_package_path = bundle / "RUNTIME-VERIFICATION.json"

    readme_path.write_text(readme, encoding="utf-8")
    build_info_path.write_text(json.dumps(build_info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    runtime_package_path.write_text(json.dumps(package_runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checksum_targets: list[Path] = [executable, readme_path, build_info_path, runtime_package_path]
    for relative in critical_files:
        target = bundle / Path(relative.replace("\\", os.sep))
        if not target.is_file():
            raise FileNotFoundError(target)
        checksum_targets.append(target)

    checksums = []
    seen: set[Path] = set()
    for target in checksum_targets:
        target = target.resolve()
        if target in seen:
            continue
        seen.add(target)
        relative = target.relative_to(bundle).as_posix()
        checksums.append(f"{sha256(target)} *{relative}")
    checksum_path = bundle / "SHA256SUMS.txt"
    checksum_path.write_text("\n".join(checksums) + "\n", encoding="utf-8")

    summary = {
        "release": build_info["release"],
        "built_at_utc": built_at,
        "source_revision": args.git_sha,
        "executable_sha256": exe_hash,
        "versions": versions,
        "torch_compiled_arch_flags": runtime.get("torch_compiled_arch_flags"),
        "physical_rtx_50_gpu_tested": False,
        "metadata_files": [
            readme_path.name,
            build_info_path.name,
            runtime_package_path.name,
            checksum_path.name,
        ],
    }
    (report_dir / "release-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for path in (readme_path, build_info_path, runtime_package_path, checksum_path):
        (report_dir / path.name).write_bytes(path.read_bytes())

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
