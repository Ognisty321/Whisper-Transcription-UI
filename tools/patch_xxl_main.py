#!/usr/bin/env python3
"""Patch the r245.4 ``--diarize`` + ``--postfix`` path bug in frozen bytecode.

The abandoned code computes a postfixed output name from the full input path,
then prepends ``dirname(input)`` a second time. It also overwrites
``audio_path`` before looking up ``diarization_output[audio_path]``, whose key
is the original input path.

The narrowly verified patch repurposes the existing local ``rrroot`` to retain
the original path, builds the corrected postfixed path, and uses ``rrroot`` for
the diarization lookup. No source decompilation or broad rewriting is used.
"""

from __future__ import annotations

import argparse
import dis
import hashlib
import json
import marshal
import ntpath
import opcode
import shutil
import types
from pathlib import Path
from typing import Any

ISSUE_URL = "https://github.com/Purfview/whisper-standalone-win/issues/569"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _find_sequence(
    code: types.CodeType,
    first_line: int,
    expected: list[tuple[str, object | None]],
) -> list[dis.Instruction] | None:
    instructions = list(dis.get_instructions(code))
    # ``starts_line`` is set only on the first instruction belonging to a
    # source line. The diarization lookup is nested in a longer call whose
    # first instruction starts line 2275, while the three-instruction
    # subexpression itself has ``starts_line=None``. Track the effective line
    # inherited from the preceding instruction instead of requiring the first
    # opcode in the target block to carry the line marker itself.
    effective_lines: list[int | None] = []
    current_line: int | None = None
    for instruction in instructions:
        if instruction.starts_line is not None:
            current_line = instruction.starts_line
        effective_lines.append(current_line)

    matches: list[list[dis.Instruction]] = []
    for index in range(len(instructions) - len(expected) + 1):
        block = instructions[index:index + len(expected)]
        if effective_lines[index] != first_line:
            continue
        valid = True
        for instruction, (opname, argval) in zip(block, expected):
            if instruction.opname != opname:
                valid = False
                break
            if argval is not None and instruction.argval != argval:
                valid = False
                break
        if valid:
            matches.append(block)
    if len(matches) > 1:
        raise RuntimeError(
            f"Ambiguous bytecode pattern at effective source line {first_line}: "
            f"found {len(matches)} matches"
        )
    return matches[0] if matches else None


def _description(block: list[dis.Instruction]) -> list[str]:
    return [f"{item.offset}: {item.opname} {item.argrepr}".rstrip() for item in block]


def _set_nop(raw: bytearray, instruction: dis.Instruction) -> None:
    if instruction.offset + 1 >= len(raw):
        raise RuntimeError(f"Invalid bytecode offset {instruction.offset}")
    if raw[instruction.offset] != instruction.opcode:
        raise RuntimeError(f"Opcode changed at offset {instruction.offset}")
    raw[instruction.offset] = opcode.opmap["NOP"]
    raw[instruction.offset + 1] = 0


def _patch_cli(code: types.CodeType, qualname: str) -> tuple[types.CodeType, dict[str, Any]]:
    original_path = _find_sequence(
        code,
        2246,
        [
            ("LOAD_GLOBAL", "os"),
            ("LOAD_ATTR", "path"),
            ("LOAD_METHOD", "dirname"),
            ("LOAD_FAST", "audio_path"),
            ("CALL_METHOD", None),
            ("STORE_FAST", "rrroot"),
        ],
    )
    output_path = _find_sequence(
        code,
        2249,
        [
            ("LOAD_FAST", "rrroot"),
            ("LOAD_FAST", "nnname"),
            ("BINARY_ADD", None),
            ("LOAD_FAST", "eeext"),
            ("BINARY_ADD", None),
            ("STORE_FAST", "audio_path"),
        ],
    )
    lookup = _find_sequence(
        code,
        2275,
        [
            ("LOAD_FAST", "diarization_output"),
            ("LOAD_FAST", "audio_path"),
            ("BINARY_SUBSCR", None),
        ],
    )

    already_original = _find_sequence(
        code,
        2246,
        [
            ("NOP", None),
            ("NOP", None),
            ("NOP", None),
            ("LOAD_FAST", "audio_path"),
            ("NOP", None),
            ("STORE_FAST", "rrroot"),
        ],
    )
    already_output = _find_sequence(
        code,
        2249,
        [
            ("NOP", None),
            ("LOAD_FAST", "nnname"),
            ("NOP", None),
            ("LOAD_FAST", "eeext"),
            ("BINARY_ADD", None),
            ("STORE_FAST", "audio_path"),
        ],
    )
    already_lookup = _find_sequence(
        code,
        2275,
        [
            ("LOAD_FAST", "diarization_output"),
            ("LOAD_FAST", "rrroot"),
            ("BINARY_SUBSCR", None),
        ],
    )

    if already_original and already_output and already_lookup:
        return code, {
            "qualname": qualname,
            "status": "already_patched",
            "issue": ISSUE_URL,
            "original_path_block": _description(already_original),
            "output_path_block": _description(already_output),
            "lookup_block": _description(already_lookup),
        }
    if not (original_path and output_path and lookup):
        raise RuntimeError(
            "Expected unmodified r245.4 bytecode patterns were not all found: "
            f"save_original={bool(original_path)}, output_path={bool(output_path)}, "
            f"diarization_lookup={bool(lookup)}"
        )

    audio_index = code.co_varnames.index("audio_path")
    root_index = code.co_varnames.index("rrroot")
    if audio_index > 255 or root_index > 255:
        raise RuntimeError("Target local variable requires EXTENDED_ARG; refusing unsafe patch")
    if lookup[1].arg != audio_index:
        raise RuntimeError(
            f"Unexpected audio_path local index at offset {lookup[1].offset}: "
            f"{lookup[1].arg} != {audio_index}"
        )

    before = {
        "original_path_block": _description(original_path),
        "output_path_block": _description(output_path),
        "lookup_block": _description(lookup),
    }
    raw = bytearray(code.co_code)

    # rrroot = audio_path (save the dictionary key before audio_path changes).
    for item in (original_path[0], original_path[1], original_path[2], original_path[4]):
        _set_nop(raw, item)

    # audio_path = nnname + eeext (nnname already contains the full path stem).
    for item in (output_path[0], output_path[2]):
        _set_nop(raw, item)

    # diarization_output[rrroot] instead of diarization_output[audio_path].
    if raw[lookup[1].offset] != opcode.opmap["LOAD_FAST"]:
        raise RuntimeError("Diarization lookup opcode changed before patch")
    raw[lookup[1].offset + 1] = root_index

    patched = code.replace(co_code=bytes(raw))
    after_original = _find_sequence(
        patched,
        2246,
        [
            ("NOP", None), ("NOP", None), ("NOP", None),
            ("LOAD_FAST", "audio_path"), ("NOP", None), ("STORE_FAST", "rrroot"),
        ],
    )
    after_output = _find_sequence(
        patched,
        2249,
        [
            ("NOP", None), ("LOAD_FAST", "nnname"), ("NOP", None),
            ("LOAD_FAST", "eeext"), ("BINARY_ADD", None), ("STORE_FAST", "audio_path"),
        ],
    )
    after_lookup = _find_sequence(
        patched,
        2275,
        [
            ("LOAD_FAST", "diarization_output"),
            ("LOAD_FAST", "rrroot"),
            ("BINARY_SUBSCR", None),
        ],
    )
    if not (after_original and after_output and after_lookup):
        raise RuntimeError("Patched bytecode failed independent structural verification")

    return patched, {
        "qualname": qualname,
        "status": "patched",
        "issue": ISSUE_URL,
        "source_lines": [2246, 2249, 2275],
        "audio_path_local_index": audio_index,
        "saved_original_local_index": root_index,
        "before": before,
        "after": {
            "original_path_block": _description(after_original),
            "output_path_block": _description(after_output),
            "lookup_block": _description(after_lookup),
        },
    }


def _patch_tree(code: types.CodeType, qualname: str = "__main__") -> tuple[types.CodeType, list[dict[str, Any]]]:
    reports: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    new_constants: list[Any] = []
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            counts[constant.co_name] = counts.get(constant.co_name, 0) + 1
            suffix = f"#{counts[constant.co_name]}" if counts[constant.co_name] > 1 else ""
            patched_child, child_reports = _patch_tree(constant, f"{qualname}.{constant.co_name}{suffix}")
            new_constants.append(patched_child)
            reports.extend(child_reports)
        else:
            new_constants.append(constant)
    if tuple(new_constants) != code.co_consts:
        code = code.replace(co_consts=tuple(new_constants))

    if code.co_name == "cli":
        code, report = _patch_cli(code, qualname)
        reports.append(report)
    return code, reports


def _semantic_fixture() -> dict[str, Any]:
    original = r"E:\AI\Whisper\Output\dialog.mp4"
    language = "uk"
    stem, extension = ntpath.splitext(original)
    corrected_output = stem + "_" + language + extension
    expected_output = r"E:\AI\Whisper\Output\dialog_uk.mp4"
    diarization_output = {original: {"segments": [1]}}
    selected = diarization_output[original]
    malformed = ntpath.dirname(original) + corrected_output
    if corrected_output != expected_output or selected["segments"] != [1] or malformed == corrected_output:
        raise RuntimeError("Independent postfix/diarization semantic fixture failed")
    return {
        "input": original,
        "language": language,
        "malformed_old_output": malformed,
        "corrected_output": corrected_output,
        "diarization_lookup_key": original,
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("marshal_file", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()

    target = args.marshal_file.resolve()
    original_bytes = target.read_bytes()
    value = marshal.loads(original_bytes)
    if not isinstance(value, types.CodeType):
        raise TypeError(f"{target} does not contain a Python code object")

    patched_code, patches = _patch_tree(value)
    if len(patches) != 1:
        raise RuntimeError(f"Expected exactly one cli() patch target, found {len(patches)}")
    patched_bytes = marshal.dumps(patched_code)

    if args.backup:
        args.backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, args.backup)
    target.write_bytes(patched_bytes)

    report = {
        "format_version": 2,
        "target": str(target),
        "python_bytecode": "CPython 3.10",
        "original_sha256": sha256(original_bytes),
        "patched_sha256": sha256(patched_bytes),
        "changed": original_bytes != patched_bytes,
        "patches": patches,
        "semantic_fixture": _semantic_fixture(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
