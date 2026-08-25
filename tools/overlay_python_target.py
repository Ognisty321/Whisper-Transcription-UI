#!/usr/bin/env python3
"""Atomically-ish overlay a pip --target directory into an XXL contents tree.

Exact top-level entries supplied by the new environment are removed first, so
old extension modules and data files cannot shadow newer wheels.  The custom
faster_whisper directory and standard library are never touched unless they are
explicitly present in the stage (the comprehensive requirements intentionally
exclude faster-whisper itself).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


SKIP_NAMES = {"bin", "Scripts", "__pycache__"}
PROTECTED_NAMES = {"faster_whisper", "xxl_original_scripts"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def directory_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    stage = args.stage.resolve()
    destination = args.destination.resolve()
    if not stage.is_dir():
        raise NotADirectoryError(stage)
    if not destination.is_dir():
        raise NotADirectoryError(destination)

    entries = [entry for entry in stage.iterdir() if entry.name not in SKIP_NAMES]
    protected = sorted(entry.name for entry in entries if entry.name in PROTECTED_NAMES)
    if protected:
        raise RuntimeError(f"Refusing to overwrite protected XXL code: {protected}")

    report: dict[str, Any] = {
        "stage": str(stage),
        "destination": str(destination),
        "removed": [],
        "installed": [],
        "skipped": sorted(SKIP_NAMES & {entry.name for entry in stage.iterdir()}),
    }

    # Remove exact staged entries and all stale dist-info records for packages
    # being installed.  Exact top-level removal also covers *.libs directories.
    stage_dist_names: set[str] = set()
    for entry in entries:
        if entry.name.endswith(".dist-info"):
            metadata = entry / "METADATA"
            if metadata.is_file():
                for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("Name:"):
                        stage_dist_names.add(line.split(":", 1)[1].strip().lower().replace("-", "_"))
                        break

    for old in list(destination.glob("*.dist-info")):
        metadata = old / "METADATA"
        old_name = ""
        if metadata.is_file():
            for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Name:"):
                    old_name = line.split(":", 1)[1].strip().lower().replace("-", "_")
                    break
        if old_name and old_name in stage_dist_names:
            size = directory_size(old)
            remove_path(old)
            report["removed"].append({"name": old.name, "bytes": size, "reason": "stale-dist-info"})

    for entry in entries:
        target = destination / entry.name
        if target.exists() or target.is_symlink():
            size = directory_size(target)
            remove_path(target)
            report["removed"].append({"name": target.name, "bytes": size, "reason": "exact-stage-entry"})

    for entry in entries:
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, copy_function=shutil.copy2)
        else:
            shutil.copy2(entry, target)
        installed = {"name": entry.name, "bytes": directory_size(target)}
        if target.is_file():
            installed["sha256"] = sha256(target)
        report["installed"].append(installed)

    report["removed_bytes"] = sum(item["bytes"] for item in report["removed"])
    report["installed_bytes"] = sum(item["bytes"] for item in report["installed"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "removed_entries": len(report["removed"]),
        "installed_entries": len(report["installed"]),
        "removed_bytes": report["removed_bytes"],
        "installed_bytes": report["installed_bytes"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
