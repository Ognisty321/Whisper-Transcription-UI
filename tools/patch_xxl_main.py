#!/usr/bin/env python3
"""Apply narrowly validated fixes to Faster-Whisper-XXL r245.4 frozen __main__.

The abandoned r245.4 code builds a postfix path as:
    dirname(audio_path) + splitext(audio_path)[0] + '_' + language + extension
Because splitext(audio_path)[0] is already an absolute/full path, dirname is
prepended twice. Later diarization_output[audio_path] raises KeyError.

This tool patches only the six-instruction expression in cli() so it becomes:
    splitext(audio_path)[0] + '_' + language + extension
The expected bytecode pattern is verified before any write.
"""

from __future__ import annotations

import argparse
import dis
import hashlib
import json
import marshal
import opcode
import shutil
import types
from pathlib import Path
from typing import Any


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def walk(code: types.CodeType, qualname: str = "__main__"):
    yield qualname, code
    counts: dict[str, int] = {}
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            counts[const.co_name] = counts.get(const.co_name, 0) + 1
            suffix = f"#{counts[const.co_name]}" if counts[const.co_name] > 1 else ""
            yield from walk(const, f"{qualname}.{const.co_name}{suffix}")


def find_postfix_pattern(code: types.CodeType) -> tuple[list[dis.Instruction], int] | None:
    instructions = list(dis.get_instructions(code))
    expected = [
        ("LOAD_FAST", "rrroot"),
        ("LOAD_FAST", "nnname"),
        ("BINARY_ADD", None),
        ("LOAD_FAST", "eeext"),
        ("BINARY_ADD", None),
        ("STORE_FAST", "audio_path"),
    ]
    for index in range(len(instructions) - len(expected) + 1):
        block = instructions[index:index + len(expected)]
        ok = True
        for ins, (opname, argval) in zip(block, expected):
            if ins.opname != opname:
                ok = False
                break
            if argval is not None and ins.argval != argval:
                ok = False
                break
        if not ok:
            continue
        lines = {ins.starts_line for ins in block if ins.starts_line is not None}
        if lines and not any(2244 <= line <= 2250 for line in lines):
            continue
        return block, index
    return None


def patch_code_tree(code: types.CodeType, qualname: str = "__main__") -> tuple[types.CodeType, list[dict[str, Any]]]:
    patches: list[dict[str, Any]] = []
    new_consts: list[Any] = []
    child_counts: dict[str, int] = {}
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            child_counts[const.co_name] = child_counts.get(const.co_name, 0) + 1
            suffix = f"#{child_counts[const.co_name]}" if child_counts[const.co_name] > 1 else ""
            new_child, child_patches = patch_code_tree(const, f"{qualname}.{const.co_name}{suffix}")
            new_consts.append(new_child)
            patches.extend(child_patches)
        else:
            new_consts.append(const)
    if tuple(new_consts) != code.co_consts:
        code = code.replace(co_consts=tuple(new_consts))

    if code.co_name != "cli":
        return code, patches

    match = find_postfix_pattern(code)
    if match is None:
        # Accept an already-patched pattern only if the two exact NOPs are present.
        instructions = list(dis.get_instructions(code))
        for index in range(len(instructions) - 6 + 1):
            block = instructions[index:index + 6]
            if (
                block[0].opname == "NOP"
                and block[1].opname == "LOAD_FAST" and block[1].argval == "nnname"
                and block[2].opname == "NOP"
                and block[3].opname == "LOAD_FAST" and block[3].argval == "eeext"
                and block[4].opname == "BINARY_ADD"
                and block[5].opname == "STORE_FAST" and block[5].argval == "audio_path"
            ):
                patches.append({
                    "qualname": qualname,
                    "status": "already_patched",
                    "offsets": [block[0].offset, block[2].offset],
                })
                return code, patches
        raise RuntimeError("Expected r245.4 postfix path bytecode pattern was not found in cli()")

    block, _ = match
    first, _, third, _, _, _ = block
    raw = bytearray(code.co_code)
    nop = opcode.opmap["NOP"]
    for ins in (first, third):
        if ins.offset + 1 >= len(raw):
            raise RuntimeError(f"Invalid patch offset {ins.offset}")
        if raw[ins.offset] != ins.opcode:
            raise RuntimeError(f"Opcode changed at offset {ins.offset}")
        raw[ins.offset] = nop
        raw[ins.offset + 1] = 0

    patched = code.replace(co_code=bytes(raw))
    verify = list(dis.get_instructions(patched))
    by_offset = {ins.offset: ins for ins in verify}
    if by_offset[first.offset].opname != "NOP" or by_offset[third.offset].opname != "NOP":
        raise RuntimeError("Post-patch bytecode verification failed")

    patches.append({
        "qualname": qualname,
        "status": "patched",
        "source_lines": [2246, 2247, 2248, 2249, 2275],
        "offsets": [first.offset, third.offset],
        "before": [f"{ins.opname} {ins.argrepr}".strip() for ins in block],
        "after": [
            f"{by_offset[ins.offset].opname} {by_offset[ins.offset].argrepr}".strip()
            for ins in block
        ],
        "issue": "https://github.com/Purfview/whisper-standalone-win/issues/569",
    })
    return patched, patches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("marshal_file", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()

    path = args.marshal_file.resolve()
    original_bytes = path.read_bytes()
    code = marshal.loads(original_bytes)
    if not isinstance(code, types.CodeType):
        raise TypeError(f"{path} does not contain a Python code object")

    patched_code, patches = patch_code_tree(code)
    patch_events = [item for item in patches if item.get("status") == "patched"]
    already = [item for item in patches if item.get("status") == "already_patched"]
    if len(patch_events) + len(already) != 1:
        raise RuntimeError(f"Expected exactly one target cli(), got {patches!r}")

    patched_bytes = marshal.dumps(patched_code)
    if args.backup:
        args.backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, args.backup)
    path.write_bytes(patched_bytes)

    # Independent semantic regression fixture for the exact expression.
    sample = r"E:\AI\Whisper\Output\dialog.mp4"
    import os
    lang = "uk"
    root = os.path.dirname(sample)
    name = os.path.splitext(sample)[0] + "_" + lang
    ext = os.path.splitext(sample)[1]
    buggy = root + name + ext
    fixed = name + ext
    expected = r"E:\AI\Whisper\Output\dialog_uk.mp4"
    if fixed != expected or buggy == expected:
        raise RuntimeError("Postfix path semantic fixture failed")

    report = {
        "format_version": 1,
        "target": str(path),
        "python_bytecode": "CPython 3.10",
        "original_sha256": sha256(original_bytes),
        "patched_sha256": sha256(patched_bytes),
        "changed": original_bytes != patched_bytes,
        "patches": patches,
        "semantic_fixture": {
            "input": sample,
            "language": lang,
            "buggy_result": buggy,
            "fixed_result": fixed,
            "expected": expected,
            "passed": True,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
