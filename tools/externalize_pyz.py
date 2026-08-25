#!/usr/bin/env python3
"""Externalize a PyInstaller application's embedded PYZ modules.

The source application is preserved as bytecode. No decompilation is performed.
The generated .pyc files are importable by the same CPython minor version.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import marshal
import os
import shutil
import struct
import sys
import types
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader, PKG_ITEM_PYSOURCE, PKG_ITEM_PYZ
from PyInstaller.loader.pyimod01_archive import PYZ_ITEM_MODULE, PYZ_ITEM_NSPKG, PYZ_ITEM_PKG


PYC_HEADER = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, 0, 0)


def module_target(root: Path, name: str, typecode: int) -> Path | None:
    parts = name.split(".")
    if typecode == PYZ_ITEM_MODULE:
        return root.joinpath(*parts[:-1], parts[-1] + ".pyc")
    if typecode == PYZ_ITEM_PKG:
        return root.joinpath(*parts, "__init__.pyc")
    if typecode == PYZ_ITEM_NSPKG:
        root.joinpath(*parts).mkdir(parents=True, exist_ok=True)
        return None
    raise ValueError(f"Unsupported PYZ typecode {typecode!r} for {name!r}")


def write_pyc(path: Path, code: types.CodeType) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("wb") as stream:
        stream.write(PYC_HEADER)
        marshal.dump(code, stream)
    os.replace(tmp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("contents_dir", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scripts-dir", type=Path, required=True)
    args = parser.parse_args()

    executable = args.executable.resolve()
    contents_dir = args.contents_dir.resolve()
    scripts_dir = args.scripts_dir.resolve()
    manifest_path = args.manifest.resolve()

    if not executable.is_file():
        raise FileNotFoundError(executable)
    if not contents_dir.is_dir():
        raise NotADirectoryError(contents_dir)

    scripts_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    archive = CArchiveReader(str(executable))
    pyz_names = [name for name, entry in archive.toc.items() if entry[-1] == PKG_ITEM_PYZ]
    if len(pyz_names) != 1:
        raise RuntimeError(f"Expected exactly one PYZ archive, found {pyz_names!r}")

    pyz = archive.open_embedded_archive(pyz_names[0])
    counts = {"module": 0, "package": 0, "namespace": 0, "skipped": 0}
    written: list[str] = []

    for name in sorted(pyz.toc):
        typecode, _offset, _length = pyz.toc[name]
        if typecode == PYZ_ITEM_NSPKG:
            module_target(contents_dir, name, typecode)
            counts["namespace"] += 1
            continue
        if typecode not in (PYZ_ITEM_MODULE, PYZ_ITEM_PKG):
            counts["skipped"] += 1
            continue

        code = pyz.extract(name)
        if not isinstance(code, types.CodeType):
            raise TypeError(f"PYZ entry {name!r} did not contain a code object: {type(code)!r}")
        target = module_target(contents_dir, name, typecode)
        assert target is not None
        write_pyc(target, code)
        written.append(str(target.relative_to(contents_dir)))
        counts["package" if typecode == PYZ_ITEM_PKG else "module"] += 1

    script_order: list[str] = []
    for name, entry in archive.toc.items():
        typecode = entry[-1]
        if typecode != PKG_ITEM_PYSOURCE or name == "pyiboot01_bootstrap":
            continue
        data = archive.extract(name)
        code = marshal.loads(data)
        if not isinstance(code, types.CodeType):
            raise TypeError(f"CArchive script {name!r} did not contain a code object: {type(code)!r}")
        target = scripts_dir / f"{name}.marshal"
        target.write_bytes(data)
        script_order.append(name)

    if "__main__" not in script_order:
        raise RuntimeError("Original __main__ script was not found")

    manifest = {
        "source_executable": executable.name,
        "python_magic_hex": importlib.util.MAGIC_NUMBER.hex(),
        "python_version": sys.version,
        "pyz_archive": pyz_names[0],
        "counts": counts,
        "script_order": script_order,
        "written_files": len(written),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
