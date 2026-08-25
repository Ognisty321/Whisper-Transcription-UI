#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path


def norm_dist(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def dist_name_from_metadata(dist_info: Path) -> str:
    metadata = dist_info / "METADATA"
    if metadata.is_file():
        for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Name:"):
                return line.split(":", 1)[1].strip()
    return dist_info.name.rsplit(".dist-info", 1)[0].rsplit("-", 1)[0]


def safe_top_name(name: str) -> bool:
    name = name.strip()
    if not name or name in {".", "..", "bin", "Scripts"}:
        return False
    if name.startswith(".") or "/" in name or "\\" in name:
        return False
    # Top-level wheel entries are package/module/file basenames only.
    return re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name) is not None


def infer_top_levels(stage: Path, dist_info: Path) -> set[str]:
    top = dist_info / "top_level.txt"
    names: set[str] = set()
    if top.is_file():
        for line in top.read_text(encoding="utf-8", errors="replace").splitlines():
            name = line.strip()
            if safe_top_name(name):
                names.add(name)
    record = dist_info / "RECORD"
    if record.is_file():
        try:
            rows = csv.reader(record.read_text(encoding="utf-8", errors="replace").splitlines())
            for row in rows:
                if not row:
                    continue
                path = row[0].replace("\\", "/")
                first = path.split("/", 1)[0].strip()
                if not safe_top_name(first):
                    continue
                if first.endswith(".dist-info") or first.endswith(".data"):
                    continue
                if "." in first and not first.endswith((".py", ".pyc", ".pyd", ".dll")):
                    continue
                names.add(first)
        except Exception:
            pass
    return names


def ensure_inside(contents: Path, candidate: Path) -> Path:
    root = contents.resolve()
    resolved = candidate.resolve()
    if resolved == root:
        raise RuntimeError(f"Refusing to modify contents root itself: {candidate}")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Refusing path outside contents root: {candidate} -> {resolved}") from exc
    return resolved


def remove_old_distribution(contents: Path, dist_name: str) -> list[str]:
    removed = []
    nd = norm_dist(dist_name)
    if not contents.is_dir():
        raise NotADirectoryError(contents)
    for child in list(contents.iterdir()):
        if child.is_dir() and child.name.endswith((".dist-info", ".egg-info")):
            stem = child.name.rsplit(".dist-info", 1)[0].rsplit(".egg-info", 1)[0]
            if norm_dist(stem).startswith(nd + "-") or norm_dist(stem) == nd:
                ensure_inside(contents, child)
                shutil.rmtree(child, ignore_errors=True)
                removed.append(child.name)
    return removed


def remove_top_level(contents: Path, top: str) -> list[str]:
    if not safe_top_name(top):
        raise RuntimeError(f"Unsafe top-level wheel entry rejected: {top!r}")
    removed = []
    candidates = [contents / top]
    p = Path(top)
    if p.suffix in {".py", ".pyc", ".pyd", ".dll"}:
        stem = p.stem
        candidates += [contents / (stem + ".py"), contents / (stem + ".pyc")]
    else:
        candidates += [contents / (top + ".py"), contents / (top + ".pyc")]
    seen = set()
    for c in candidates:
        resolved = ensure_inside(contents, c)
        if resolved in seen:
            continue
        seen.add(resolved)
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=False)
            removed.append(c.name)
        elif c.exists():
            c.unlink()
            removed.append(c.name)
    return removed


TORCHAUDIO_IO_COMPAT = r'''

# XXL compatibility backport -------------------------------------------------
# pyannote.audio 3.x still uses the legacy TorchAudio file-I/O API. TorchAudio
# deprecated it in 2.8 and removed it in 2.9+, while RTX 50 support requires a
# much newer coherent Torch/TorchAudio stack. Keep pyannote 3.x's public API
# (which the custom XXL bytecode expects) and emulate only the removed I/O
# surface through SoundFile. Resampling still uses torchaudio.functional.
if not hasattr(torchaudio, "AudioMetaData") or not hasattr(torchaudio, "load"):
    from typing import NamedTuple as _XXLNamedTuple
    import re as _xxl_re
    import soundfile as _xxl_sf
    import torch as _xxl_torch

    class _XXLAudioMetaData(_XXLNamedTuple):
        sample_rate: int
        num_frames: int
        num_channels: int
        bits_per_sample: int
        encoding: str

    def _xxl_bits_per_sample(subtype):
        subtype = subtype or ""
        match = _xxl_re.search(r"(8|16|24|32|64)", subtype)
        return int(match.group(1)) if match else 0

    def _xxl_audio_info(uri, backend=None, format=None):
        info = _xxl_sf.info(uri)
        return _XXLAudioMetaData(
            sample_rate=int(info.samplerate),
            num_frames=int(info.frames),
            num_channels=int(info.channels),
            bits_per_sample=_xxl_bits_per_sample(info.subtype),
            encoding=str(info.subtype or info.format or ""),
        )

    def _xxl_audio_load(
        uri,
        frame_offset=0,
        num_frames=-1,
        normalize=True,
        channels_first=True,
        format=None,
        buffer_size=4096,
        backend=None,
    ):
        frames = -1 if num_frames is None or int(num_frames) < 0 else int(num_frames)
        data, sample_rate = _xxl_sf.read(
            uri,
            start=max(0, int(frame_offset)),
            frames=frames,
            dtype="float32",
            always_2d=True,
        )
        if channels_first:
            data = data.T.copy()
        else:
            data = data.copy()
        return _xxl_torch.from_numpy(data), int(sample_rate)

    if not hasattr(torchaudio, "AudioMetaData"):
        torchaudio.AudioMetaData = _XXLAudioMetaData
    if not hasattr(torchaudio, "list_audio_backends"):
        torchaudio.list_audio_backends = lambda: ["soundfile"]
    if not hasattr(torchaudio, "info"):
        torchaudio.info = _xxl_audio_info
    if not hasattr(torchaudio, "load"):
        torchaudio.load = _xxl_audio_load
# End XXL compatibility backport ---------------------------------------------
'''


def patch_pyannote_for_modern_torchaudio(contents: Path) -> dict:
    io_path = contents / "pyannote" / "audio" / "core" / "io.py"
    result = {"path": str(io_path), "patched": False}
    if not io_path.is_file():
        result["reason"] = "pyannote audio io.py not present"
        return result
    text = io_path.read_text(encoding="utf-8", errors="strict")
    if "XXL compatibility backport" in text:
        result["reason"] = "already patched"
        return result
    marker = "import torchaudio\n"
    if marker not in text:
        result["reason"] = "torchaudio import marker not found"
        return result
    text = text.replace(marker, marker + TORCHAUDIO_IO_COMPAT, 1)
    io_path.write_text(text, encoding="utf-8")
    result["patched"] = True
    result["reason"] = "legacy AudioMetaData/list_audio_backends/info/load emulated via SoundFile"
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", type=Path)
    ap.add_argument("contents", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    stage = args.stage.resolve()
    contents = args.contents.resolve()
    if not stage.is_dir():
        raise NotADirectoryError(stage)
    if not contents.is_dir():
        raise NotADirectoryError(contents)

    report = {"stage": str(stage), "contents": str(contents), "distributions": []}
    dist_infos = sorted(stage.glob("*.dist-info"), key=lambda p: p.name.lower())
    for di in dist_infos:
        dist = dist_name_from_metadata(di)
        tops = sorted(infer_top_levels(stage, di))
        entry = {"distribution": dist, "dist_info": di.name, "top_levels": tops, "removed": []}
        entry["removed"].extend(remove_old_distribution(contents, dist))
        for top in tops:
            entry["removed"].extend(remove_top_level(contents, top))
        report["distributions"].append(entry)

    # Copy stage only into the exact contents directory. Refuse if it vanished
    # during cleanup; this turns malformed wheel metadata into a hard failure.
    if not contents.is_dir():
        raise RuntimeError(f"Contents directory disappeared during replacement: {contents}")
    for child in stage.iterdir():
        dst = contents / child.name
        ensure_inside(contents, dst)
        if child.is_dir():
            shutil.copytree(child, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(child, dst)

    report["compatibility_patches"] = {
        "pyannote_torchaudio_legacy_io": patch_pyannote_for_modern_torchaudio(contents)
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
