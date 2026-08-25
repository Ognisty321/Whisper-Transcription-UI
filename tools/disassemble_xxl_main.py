#!/usr/bin/env python3
"""Index and disassemble selected code objects from externalized XXL __main__."""

from __future__ import annotations

import argparse
import dis
import json
import marshal
import types
from pathlib import Path
from typing import Any, Iterator


KEYWORDS = {
    "postfix", "diar", "pbar", "progress", "output_dir", "output_format",
    "unload_model", "batch", "cuda", "compute_type", "vad", "mdx",
}


def walk(code: types.CodeType, qualname: str = "__main__") -> Iterator[tuple[str, types.CodeType]]:
    yield qualname, code
    counts: dict[str, int] = {}
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            counts[const.co_name] = counts.get(const.co_name, 0) + 1
            suffix = f"#{counts[const.co_name]}" if counts[const.co_name] > 1 else ""
            yield from walk(const, f"{qualname}.{const.co_name}{suffix}")


def line_bounds(code: types.CodeType) -> tuple[int, int]:
    lines = [line for _, _, line in code.co_lines() if line is not None]
    return (min(lines) if lines else code.co_firstlineno, max(lines) if lines else code.co_firstlineno)


def interesting_strings(code: types.CodeType) -> list[str]:
    strings: list[str] = []
    for const in code.co_consts:
        if isinstance(const, str):
            lower = const.lower()
            if any(keyword in lower for keyword in KEYWORDS):
                strings.append(const)
    return strings


def format_disassembly(qualname: str, code: types.CodeType) -> str:
    low, high = line_bounds(code)
    rows = [
        "=" * 120,
        f"QUALNAME: {qualname}",
        f"NAME: {code.co_name}",
        f"FILENAME: {code.co_filename}",
        f"LINES: {low}-{high}",
        f"ARGS: posonly={code.co_posonlyargcount} positional={code.co_argcount} kwonly={code.co_kwonlyargcount}",
        f"VARNAMES: {code.co_varnames}",
        f"NAMES: {code.co_names}",
        f"FREEVARS: {code.co_freevars}",
        f"CELLVARS: {code.co_cellvars}",
        "-" * 120,
    ]
    current_line = None
    for ins in dis.get_instructions(code):
        if ins.starts_line is not None:
            current_line = ins.starts_line
        marker = ">>>" if current_line in {2087, 2160, 2191, 2275, 2324} else "   "
        rows.append(
            f"{marker} line={str(current_line):>5} offset={ins.offset:>6} "
            f"{ins.opname:<30} {ins.argrepr}"
        )
    rows.append("")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("marshal_file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    code = marshal.loads(args.marshal_file.read_bytes())
    if not isinstance(code, types.CodeType):
        raise TypeError("marshal file does not contain a code object")

    index: list[dict[str, Any]] = []
    selected: list[tuple[str, types.CodeType]] = []
    all_strings: list[dict[str, Any]] = []
    for qualname, item in walk(code):
        low, high = line_bounds(item)
        strings = interesting_strings(item)
        entry = {
            "qualname": qualname,
            "name": item.co_name,
            "filename": item.co_filename,
            "first_line": item.co_firstlineno,
            "line_low": low,
            "line_high": high,
            "argcount": item.co_argcount,
            "kwonlyargcount": item.co_kwonlyargcount,
            "varnames": list(item.co_varnames),
            "names": list(item.co_names),
            "freevars": list(item.co_freevars),
            "cellvars": list(item.co_cellvars),
            "interesting_strings": strings,
        }
        index.append(entry)
        if strings:
            all_strings.append({"qualname": qualname, "strings": strings})
        name_l = item.co_name.lower()
        if (
            name_l in {"cli", "pbar_delayed", "main"}
            or "diar" in name_l
            or "postfix" in name_l
            or low <= 2275 <= high
            or low <= 2087 <= high
        ):
            selected.append((qualname, item))

    (output_dir / "main-code-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "main-interesting-strings.json").write_text(
        json.dumps(all_strings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "main-selected-disassembly.txt").write_text(
        "\n".join(format_disassembly(name, item) for name, item in selected), encoding="utf-8"
    )

    # Create a standard timestamp-based .pyc wrapper for external decompilers.
    import importlib.util
    pyc = importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(code)
    (output_dir / "xxl-main.pyc").write_bytes(pyc)

    print(json.dumps({
        "code_objects": len(index),
        "selected": len(selected),
        "output_dir": str(output_dir),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
