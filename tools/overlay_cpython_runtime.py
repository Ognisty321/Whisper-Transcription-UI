#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

EXCLUDED_DIRS = {
    "__pycache__", "test", "tests", "idlelib", "turtledemo", "ensurepip", "venv",
}
EXCLUDED_NATIVE_PREFIXES = ("_test", "xxlimited", "_ctypes_test")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def should_skip_source(path: Path, lib_root: Path) -> bool:
    rel = path.relative_to(lib_root)
    return any(part.lower() in EXCLUDED_DIRS for part in rel.parts)


def remove_stale_pyc(contents: Path, rel_py: Path) -> list[str]:
    removed: list[str] = []
    # Externalized PyInstaller modules are stored either as module.pyc or
    # package/__init__.pyc. New source must win deterministically, so delete
    # same-location stale bytecode produced by the original Python 3.10.11 bundle.
    target_pyc = contents / rel_py.with_suffix(".pyc")
    if target_pyc.is_file():
        target_pyc.unlink()
        removed.append(str(target_pyc.relative_to(contents)))
    cache_dir = (contents / rel_py).parent / "__pycache__"
    if cache_dir.is_dir():
        stem = rel_py.stem + "."
        for p in cache_dir.glob(stem + "*.pyc"):
            p.unlink()
            removed.append(str(p.relative_to(contents)))
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cpython_source", type=Path)
    ap.add_argument("build_dir", type=Path)
    ap.add_argument("contents", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    source = args.cpython_source.resolve()
    build = args.build_dir.resolve()
    contents = args.contents.resolve()
    lib = source / "Lib"
    if not lib.is_dir():
        raise NotADirectoryError(lib)
    if not build.is_dir():
        raise NotADirectoryError(build)
    if not contents.is_dir():
        raise NotADirectoryError(contents)

    report: dict = {
        "cpython_source": str(source),
        "build_dir": str(build),
        "contents": str(contents),
        "stdlib_sources_copied": 0,
        "stale_pyc_removed": [],
        "native_files": {},
    }

    for src in sorted(lib.rglob("*.py")):
        if should_skip_source(src, lib):
            continue
        rel = src.relative_to(lib)
        report["stale_pyc_removed"].extend(remove_stale_pyc(contents, rel))
        dst = contents / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        report["stdlib_sources_copied"] += 1

    # CPython PCbuild copies the runtime DLLs and third-party DLL dependencies
    # used by extension modules into PCbuild/amd64. Copy the complete runtime set,
    # excluding only CPython's internal test modules.
    for src in sorted(build.iterdir()):
        if not src.is_file() or src.suffix.lower() not in {".dll", ".pyd"}:
            continue
        if src.name.lower().startswith(EXCLUDED_NATIVE_PREFIXES):
            continue
        dst = contents / src.name
        shutil.copy2(src, dst)
        report["native_files"][src.name] = {
            "size": dst.stat().st_size,
            "sha256": sha256(dst),
        }

    required = [
        "python310.dll", "_ssl.pyd", "_hashlib.pyd", "_sqlite3.pyd", "zlib.pyd",
        "libssl-1_1.dll", "libcrypto-1_1.dll",
    ]
    missing = [name for name in required if not (contents / name).is_file()]
    if missing:
        raise FileNotFoundError(f"CPython runtime overlay missing required files: {missing}")

    report["required_files"] = {
        name: {"size": (contents / name).stat().st_size, "sha256": sha256(contents / name)}
        for name in required
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
