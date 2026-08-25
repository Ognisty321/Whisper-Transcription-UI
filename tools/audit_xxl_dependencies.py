#!/usr/bin/env python3
"""Audit embedded Faster-Whisper-XXL dependencies without modifying the bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


PROBES: list[tuple[str, str, list[str]]] = [
    ("faster-whisper", "faster_whisper", ["__version__"]),
    ("ctranslate2", "ctranslate2", ["__version__"]),
    ("torch", "torch", ["__version__"]),
    ("torchvision", "torchvision", ["__version__"]),
    ("torchaudio", "torchaudio", ["__version__"]),
    ("onnxruntime-gpu", "onnxruntime", ["__version__"]),
    ("transformers", "transformers", ["__version__"]),
    ("tokenizers", "tokenizers", ["__version__"]),
    ("huggingface-hub", "huggingface_hub", ["__version__"]),
    ("safetensors", "safetensors", ["__version__"]),
    ("av", "av", ["__version__"]),
    ("numpy", "numpy", ["__version__", "version.version"]),
    ("scipy", "scipy", ["__version__"]),
    ("scikit-learn", "sklearn", ["__version__"]),
    ("pandas", "pandas", ["__version__"]),
    ("librosa", "librosa", ["__version__"]),
    ("numba", "numba", ["__version__"]),
    ("llvmlite", "llvmlite", ["__version__"]),
    ("soundfile", "soundfile", ["__version__"]),
    ("soxr", "soxr", ["__version__"]),
    ("requests", "requests", ["__version__"]),
    ("urllib3", "urllib3", ["__version__"]),
    ("certifi", "certifi", ["__version__"]),
    ("charset-normalizer", "charset_normalizer", ["__version__"]),
    ("idna", "idna", ["__version__"]),
    ("aiohttp", "aiohttp", ["__version__"]),
    ("yarl", "yarl", ["__version__"]),
    ("multidict", "multidict", ["__version__"]),
    ("frozenlist", "frozenlist", ["__version__"]),
    ("attrs", "attr", ["__version__"]),
    ("pyyaml", "yaml", ["__version__"]),
    ("protobuf", "google.protobuf", ["__version__"]),
    ("sympy", "sympy", ["__version__"]),
    ("packaging", "packaging", ["__version__"]),
    ("setuptools", "setuptools", ["__version__"]),
    ("wheel", "wheel", ["__version__"]),
    ("psutil", "psutil", ["__version__"]),
    ("tqdm", "tqdm", ["__version__"]),
    ("rich", "rich", ["__version__"]),
    ("coloredlogs", "coloredlogs", ["__version__"]),
    ("flatbuffers", "flatbuffers", ["__version__"]),
    ("sentencepiece", "sentencepiece", ["__version__"]),
    ("pyannote.audio", "pyannote.audio", ["__version__"]),
    ("pyannote.core", "pyannote.core", ["__version__"]),
    ("pyannote.database", "pyannote.database", ["__version__"]),
    ("pyannote.metrics", "pyannote.metrics", ["__version__"]),
    ("lightning", "lightning", ["__version__"]),
    ("pytorch-lightning", "pytorch_lightning", ["__version__"]),
    ("torchmetrics", "torchmetrics", ["__version__"]),
    ("lightning-utilities", "lightning_utilities", ["__version__"]),
    ("omegaconf", "omegaconf", ["__version__"]),
    ("hydra-core", "hydra", ["__version__"]),
    ("optuna", "optuna", ["__version__"]),
    ("sqlalchemy", "sqlalchemy", ["__version__"]),
    ("matplotlib", "matplotlib", ["__version__"]),
    ("pillow", "PIL", ["__version__"]),
    ("webrtcvad-wheels", "webrtcvad", ["__version__"]),
    ("pyreadline3", "pyreadline3", ["__version__"]),
    ("cffi", "cffi", ["__version__"]),
    ("cryptography", "cryptography", ["__version__"]),
    ("filelock", "filelock", ["__version__"]),
    ("fsspec", "fsspec", ["__version__"]),
    ("jinja2", "jinja2", ["__version__"]),
    ("markupsafe", "markupsafe", ["__version__"]),
    ("networkx", "networkx", ["__version__"]),
    ("regex", "regex", ["__version__"]),
    ("typing-extensions", "typing_extensions", ["__version__"]),
]


CHILD = r'''
import importlib, json, os, sys, traceback
from pathlib import Path
contents = Path(sys.argv[1]).resolve()
module_name = sys.argv[2]
attrs = json.loads(sys.argv[3])
dll_dirs = [contents, contents / "ctranslate2", contents / "torch" / "lib", contents / "onnxruntime" / "capi", contents / "av.libs", contents / "scipy.libs", contents / "pandas.libs"]
existing = [str(p) for p in dll_dirs if p.is_dir()]
os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])
handles = []
if os.name == "nt" and hasattr(os, "add_dll_directory"):
    for p in existing:
        try:
            handles.append(os.add_dll_directory(p))
        except OSError:
            pass
sys.path.insert(0, str(contents))
result = {"module": module_name}
try:
    module = importlib.import_module(module_name)
    result["file"] = str(getattr(module, "__file__", ""))
    value = None
    selected = None
    for attr_path in attrs:
        obj = module
        try:
            for part in attr_path.split("."):
                obj = getattr(obj, part)
            if obj is not None:
                value = str(obj)
                selected = attr_path
                break
        except Exception:
            continue
    result["version"] = value
    result["version_source"] = selected
    result["ok"] = True
except BaseException as exc:
    result["ok"] = False
    result["error"] = f"{type(exc).__name__}: {exc}"
    result["traceback"] = traceback.format_exc(limit=12)
print(json.dumps(result, ensure_ascii=False))
'''


def run_probe(contents: Path, dist_name: str, module_name: str, attrs: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, "-c", CHILD, str(contents), module_name, json.dumps(attrs)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
    except subprocess.TimeoutExpired:
        return {"distribution": dist_name, "module": module_name, "ok": False, "error": "timeout after 45 seconds"}
    output = proc.stdout.strip().splitlines()
    if not output:
        return {
            "distribution": dist_name,
            "module": module_name,
            "ok": False,
            "error": f"child exit {proc.returncode} without JSON",
            "stderr": proc.stderr[-4000:],
        }
    try:
        result = json.loads(output[-1])
    except json.JSONDecodeError:
        return {
            "distribution": dist_name,
            "module": module_name,
            "ok": False,
            "error": f"invalid child JSON; exit {proc.returncode}",
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    result["distribution"] = dist_name
    result["child_exit"] = proc.returncode
    if proc.stderr.strip():
        result["stderr_tail"] = proc.stderr[-4000:]
    return result


def release_has_usable_file(files: list[dict[str, Any]]) -> bool:
    if not files:
        return False
    py_version = Version("3.10.11")
    for entry in files:
        requires_python = entry.get("requires_python")
        if requires_python:
            try:
                if py_version not in SpecifierSet(requires_python):
                    continue
            except InvalidSpecifier:
                pass
        filename = str(entry.get("filename", "")).lower()
        packagetype = entry.get("packagetype")
        if packagetype == "bdist_wheel":
            if filename.endswith("-py3-none-any.whl") or filename.endswith("-py2.py3-none-any.whl"):
                return True
            if "win_amd64.whl" in filename and ("cp310" in filename or "abi3" in filename or "py3-none" in filename):
                return True
        elif packagetype == "sdist":
            # Keep source-only candidates visible, but prefer a wheel when selecting.
            continue
    return False


def pypi_latest_compatible(name: str) -> dict[str, Any]:
    url = f"https://pypi.org/pypi/{name}/json"
    request = urllib.request.Request(url, headers={"User-Agent": "xxl-dependency-audit/1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:
        return {"name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}

    candidates: list[Version] = []
    for raw, release_files in payload.get("releases", {}).items():
        try:
            version = Version(raw)
        except InvalidVersion:
            continue
        if version.is_prerelease or version.is_devrelease:
            continue
        if release_has_usable_file(release_files):
            candidates.append(version)
    candidates.sort(reverse=True)
    info = payload.get("info", {})
    return {
        "name": name,
        "ok": bool(candidates),
        "latest_compatible_win_cp310": str(candidates[0]) if candidates else None,
        "latest_project_release": info.get("version"),
        "requires_python": info.get("requires_python"),
        "project_url": info.get("project_url"),
    }


def scan_dist_info(contents: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in sorted(contents.glob("*.dist-info"), key=lambda p: p.name.lower()):
        metadata = path / "METADATA"
        name = None
        version = None
        if metadata.is_file():
            text = metadata.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^Name:\s*(.+)$", text, re.MULTILINE)
            if m:
                name = m.group(1).strip()
            m = re.search(r"^Version:\s*(.+)$", text, re.MULTILINE)
            if m:
                version = m.group(1).strip()
        if name is None or version is None:
            match = re.match(r"(.+?)-([0-9][^-]*)\.dist-info$", path.name)
            if match:
                name = name or match.group(1)
                version = version or match.group(2)
        found.append({"directory": path.name, "name": name, "version": version})
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contents_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    contents = args.contents_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not contents.is_dir():
        raise NotADirectoryError(contents)

    probes = [run_probe(contents, *item) for item in PROBES]
    pypi = [pypi_latest_compatible(item[0]) for item in PROBES if item[0] not in {"torch", "torchvision", "torchaudio"}]
    dist_info = scan_dist_info(contents)

    report = {
        "python": sys.version,
        "contents_dir": str(contents),
        "probe_count": len(probes),
        "successful_imports": sum(bool(item.get("ok")) for item in probes),
        "versioned_imports": sum(bool(item.get("version")) for item in probes),
        "embedded_import_probes": probes,
        "embedded_dist_info": dist_info,
        "pypi_latest_compatible": pypi,
    }
    (output_dir / "dependency-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = ["distribution\tembedded_version\timport_ok\tlatest_win_cp310\tmodule\terror"]
    latest_by_name = {item["name"]: item for item in pypi}
    for item in probes:
        latest = latest_by_name.get(item["distribution"], {})
        rows.append(
            "\t".join(
                str(value or "").replace("\t", " ").replace("\n", " ")
                for value in [
                    item["distribution"],
                    item.get("version"),
                    item.get("ok"),
                    latest.get("latest_compatible_win_cp310"),
                    item.get("module"),
                    item.get("error"),
                ]
            )
        )
    (output_dir / "dependency-audit.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    print(json.dumps({
        "successful_imports": report["successful_imports"],
        "versioned_imports": report["versioned_imports"],
        "probe_count": report["probe_count"],
        "output": str(output_dir / "dependency-audit.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
