#!/usr/bin/env python3
"""Patch known r245.4 bugs directly in the original CPython 3.10 code object.

The patch preserves bytecode length and all jump offsets. This is important because
Faster-Whisper-XXL r245.4 is distributed only as a PyInstaller executable and its
original source file is not available.
"""

from __future__ import annotations

import argparse
import dis
import hashlib
import json
import marshal
import types
from pathlib import Path
from typing import Any


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def replace_nested(code: types.CodeType, target_name: str, patcher) -> tuple[types.CodeType, list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    new_consts = []
    const_changed = False
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            nested, nested_changes = replace_nested(const, target_name, patcher)
            new_consts.append(nested)
            changes.extend(nested_changes)
            if nested is not const:
                const_changed = True
        else:
            new_consts.append(const)

    current = code.replace(co_consts=tuple(new_consts)) if const_changed else code
    if current.co_name == target_name:
        current, own_changes = patcher(current)
        changes.extend(own_changes)
    return current, changes


def patch_cli_postfix_path(code: types.CodeType) -> tuple[types.CodeType, list[dict[str, Any]]]:
    """Fix `rrroot + nnname + eeext` where nnname already contains the full path.

    Original r245.4 instructions correspond to:

        rrroot = os.path.dirname(audio_path)
        nnname = os.path.splitext(audio_path)[0] + "_" + lllang
        eeext = os.path.splitext(audio_path)[1]
        audio_path = rrroot + nnname + eeext

    The last line duplicates the directory and breaks diarization's dictionary
    lookup when --postfix is active. The correct expression is nnname + eeext.

    We convert two two-byte instructions to NOP, preserving bytecode length:
        LOAD_FAST rrroot -> NOP
        first BINARY_ADD -> NOP
    """
    instructions = list(dis.get_instructions(code))
    expected = [
        ("LOAD_FAST", "rrroot"),
        ("LOAD_FAST", "nnname"),
        ("BINARY_ADD", None),
        ("LOAD_FAST", "eeext"),
        ("BINARY_ADD", None),
        ("STORE_FAST", "audio_path"),
    ]

    matches: list[list[dis.Instruction]] = []
    for start in range(len(instructions) - len(expected) + 1):
        window = instructions[start : start + len(expected)]
        ok = True
        for ins, (opname, argval) in zip(window, expected):
            if ins.opname != opname:
                ok = False
                break
            if argval is not None and ins.argval != argval:
                ok = False
                break
        if ok:
            matches.append(window)

    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one postfix path bytecode pattern, found {len(matches)}")

    window = matches[0]
    bytecode = bytearray(code.co_code)
    nop = dis.opmap["NOP"]
    patched_offsets = [window[0].offset, window[2].offset]
    for offset in patched_offsets:
        if offset + 1 >= len(bytecode):
            raise RuntimeError(f"Invalid instruction offset {offset}")
        bytecode[offset] = nop
        bytecode[offset + 1] = 0

    patched = code.replace(co_code=bytes(bytecode))
    after = list(dis.get_instructions(patched))
    by_offset = {ins.offset: ins for ins in after}
    for offset in patched_offsets:
        if by_offset[offset].opname != "NOP":
            raise RuntimeError(f"Instruction at {offset} was not converted to NOP")

    change = {
        "patch": "r245.4-diarize-postfix-path",
        "code_name": code.co_name,
        "filename": code.co_filename,
        "line": window[0].starts_line,
        "matched_offsets": [ins.offset for ins in window],
        "patched_offsets": patched_offsets,
        "before": [f"{ins.offset}:{ins.opname} {ins.argrepr}".rstrip() for ins in window],
        "after": [
            f"{by_offset[ins.offset].offset}:{by_offset[ins.offset].opname} {by_offset[ins.offset].argrepr}".rstrip()
            for ins in window
        ],
        "semantic_change": "audio_path = rrroot + nnname + eeext  ->  audio_path = nnname + eeext",
    }
    return patched, [change]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("marshal_file", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    path = args.marshal_file.resolve()
    original_bytes = path.read_bytes()
    original = marshal.loads(original_bytes)
    if not isinstance(original, types.CodeType):
        raise TypeError(f"{path} does not contain a Python code object")

    patched, changes = replace_nested(original, "cli", patch_cli_postfix_path)
    if len(changes) != 1:
        raise RuntimeError(f"Expected one applied patch, got {len(changes)}")

    patched_bytes = marshal.dumps(patched)
    # Atomic replacement.
    temporary = path.with_suffix(path.suffix + ".patched")
    temporary.write_bytes(patched_bytes)
    temporary.replace(path)

    verification = marshal.loads(path.read_bytes())
    if not isinstance(verification, types.CodeType):
        raise RuntimeError("Patched marshal payload could not be reloaded")

    report = {
        "file": str(path),
        "python_magic_not_stored_in_marshal": True,
        "original_size": len(original_bytes),
        "patched_size": len(patched_bytes),
        "original_sha256": sha256(original_bytes),
        "patched_sha256": sha256(patched_bytes),
        "bytecode_length_preserved_for_cli": True,
        "changes": changes,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
