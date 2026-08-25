#!/usr/bin/env python3
"""Index code-object APIs in externalized .pyc files."""

from __future__ import annotations

import argparse
import dis
import hashlib
import json
import marshal
import struct
import types
from pathlib import Path
from typing import Any, Iterator


def load_pyc(path: Path) -> types.CodeType:
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"Short pyc: {path}")
    code = marshal.loads(data[16:])
    if not isinstance(code, types.CodeType):
        raise TypeError(path)
    return code


def walk(code: types.CodeType, qualname: str = "<module>") -> Iterator[tuple[str, types.CodeType]]:
    yield qualname, code
    counts: dict[str, int] = {}
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            counts[const.co_name] = counts.get(const.co_name, 0) + 1
            suffix = f"#{counts[const.co_name]}" if counts[const.co_name] > 1 else ""
            yield from walk(const, f"{qualname}.{const.co_name}{suffix}")


def signature(code: types.CodeType) -> dict[str, Any]:
    positional = code.co_posonlyargcount + code.co_argcount
    names = list(code.co_varnames[: positional + code.co_kwonlyargcount])
    return {
        "posonly": code.co_posonlyargcount,
        "positional": code.co_argcount,
        "kwonly": code.co_kwonlyargcount,
        "arg_names": names,
        "flags": code.co_flags,
    }


def top_level_stores(code: types.CodeType) -> list[str]:
    names: list[str] = []
    for ins in dis.get_instructions(code):
        if ins.opname in {"STORE_NAME", "STORE_GLOBAL"} and isinstance(ins.argval, str):
            names.append(ins.argval)
    return sorted(set(names))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    modules: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.pyc")):
        try:
            code = load_pyc(path)
        except Exception as exc:
            modules.append({"path": path.relative_to(root).as_posix(), "error": f"{type(exc).__name__}: {exc}"})
            continue
        objects = []
        for qualname, obj in walk(code):
            objects.append({
                "qualname": qualname,
                "name": obj.co_name,
                "filename": obj.co_filename,
                "first_line": obj.co_firstlineno,
                "signature": signature(obj),
                "names": list(obj.co_names),
                "freevars": list(obj.co_freevars),
                "cellvars": list(obj.co_cellvars),
                "code_sha256": hashlib.sha256(obj.co_code).hexdigest(),
            })
        modules.append({
            "path": path.relative_to(root).as_posix(),
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "top_level_names": top_level_stores(code),
            "objects": objects,
        })
    report = {"root": str(root), "module_count": len(modules), "modules": modules}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"module_count": len(modules), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
