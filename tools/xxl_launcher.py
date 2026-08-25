#!/usr/bin/env python3
"""Bootstrap the original XXL bytecode from an externalized PyInstaller bundle."""

from __future__ import annotations

import json
import marshal
import os
import sys
import types
from pathlib import Path


def _configure_dll_search(contents: Path) -> None:
    candidates = [
        contents,
        contents / "ctranslate2",
        contents / "torch" / "lib",
        contents / "onnxruntime" / "capi",
    ]
    existing = [str(path) for path in candidates if path.is_dir()]
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        # Keep handles alive for the lifetime of the process.
        globals()["_XXL_DLL_DIRECTORY_HANDLES"] = [os.add_dll_directory(path) for path in existing]


def _load_code(path: Path) -> types.CodeType:
    data = path.read_bytes()
    code = marshal.loads(data)
    if not isinstance(code, types.CodeType):
        raise TypeError(f"{path} does not contain a Python code object")
    return code


def _main() -> None:
    contents = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    scripts_dir = contents / "xxl_original_scripts"
    manifest_path = contents / "xxl_externalization_manifest.json"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing reconstruction manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    script_order = manifest.get("script_order")
    if not isinstance(script_order, list) or "__main__" not in script_order:
        raise RuntimeError("Invalid reconstruction manifest: script order is missing __main__")

    _configure_dll_search(contents)

    # PyInstaller already places its contents directory on sys.path. Put it first
    # explicitly so the externalized original modules and replaced wheels take
    # precedence over global/user installations.
    contents_text = str(contents)
    sys.path[:] = [item for item in sys.path if os.path.abspath(item or os.curdir) != os.path.abspath(contents_text)]
    sys.path.insert(0, contents_text)

    namespace = globals()
    namespace["__name__"] = "__main__"
    namespace["__package__"] = None
    namespace["__cached__"] = None

    for script_name in script_order:
        script_path = scripts_dir / f"{script_name}.marshal"
        if not script_path.is_file():
            raise FileNotFoundError(f"Missing original script bytecode: {script_path}")
        namespace["__file__"] = str(contents / f"{script_name}.py")
        exec(_load_code(script_path), namespace, namespace)


if __name__ == "__main__":
    _main()
