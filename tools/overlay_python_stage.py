#!/usr/bin/env python3
"""Transactionally overlay a pip --target staging directory into a frozen bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def dist_name(path: Path) -> str | None:
    metadata = path / "METADATA"
    if metadata.is_file():
        for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip()
    match = re.match(r"(.+?)-[0-9].*\.dist-info$", path.name, re.I)
    return match.group(1) if match else None


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def move_to_backup(path: Path, contents: Path, backup: Path, moved: list[str]) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    relative = path.relative_to(contents)
    target = backup / "original" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        remove_path(target)
    shutil.move(str(path), str(target))
    moved.append(relative.as_posix())


def apply(contents: Path, stage: Path, backup: Path, manifest: Path) -> None:
    if backup.exists():
        shutil.rmtree(backup)
    (backup / "original").mkdir(parents=True)
    moved: list[str] = []
    installed: list[str] = []
    skipped: list[str] = []

    new_distributions: set[str] = set()
    for entry in stage.iterdir():
        if entry.is_dir() and entry.name.lower().endswith(".dist-info"):
            name = dist_name(entry)
            if name:
                new_distributions.add(canonical(name))

    # Remove old metadata for distributions in this stage, regardless of version.
    for entry in list(contents.iterdir()):
        if entry.is_dir() and entry.name.lower().endswith(".dist-info"):
            name = dist_name(entry)
            if name and canonical(name) in new_distributions:
                move_to_backup(entry, contents, backup, moved)

    for source in sorted(stage.iterdir(), key=lambda p: p.name.lower()):
        name = source.name
        if name in {"bin", "Scripts", "__pycache__"}:
            skipped.append(name)
            continue
        destination = contents / name
        move_to_backup(destination, contents, backup, moved)
        if source.is_file() and source.suffix.lower() == ".py":
            move_to_backup(contents / f"{source.stem}.pyc", contents, backup, moved)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        installed.append(name)

    data: dict[str, Any] = {
        "format_version": 1,
        "contents": str(contents),
        "stage": str(stage),
        "backup": str(backup),
        "moved_original_paths": moved,
        "installed_stage_entries": installed,
        "skipped_stage_entries": skipped,
        "distributions": sorted(new_distributions),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (backup / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rollback(contents: Path, backup: Path) -> None:
    data = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    for name in data.get("installed_stage_entries", []):
        remove_path(contents / name)
    for relative in sorted(data.get("moved_original_paths", []), key=lambda x: x.count("/")):
        source = backup / "original" / Path(relative)
        destination = contents / Path(relative)
        if destination.exists() or destination.is_symlink():
            remove_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.exists() or source.is_symlink():
            shutil.move(str(source), str(destination))


def commit(backup: Path) -> None:
    if backup.exists():
        shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("contents", type=Path)
    p_apply.add_argument("stage", type=Path)
    p_apply.add_argument("backup", type=Path)
    p_apply.add_argument("--manifest", type=Path, required=True)
    p_rollback = sub.add_parser("rollback")
    p_rollback.add_argument("contents", type=Path)
    p_rollback.add_argument("backup", type=Path)
    p_commit = sub.add_parser("commit")
    p_commit.add_argument("backup", type=Path)
    args = parser.parse_args()

    if args.command == "apply":
        apply(args.contents.resolve(), args.stage.resolve(), args.backup.resolve(), args.manifest.resolve())
    elif args.command == "rollback":
        rollback(args.contents.resolve(), args.backup.resolve())
    else:
        commit(args.backup.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
