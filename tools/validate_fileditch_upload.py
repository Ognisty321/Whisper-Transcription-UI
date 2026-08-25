#!/usr/bin/env python3
"""Validate a FileDitch API response against the uploaded archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("response", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    response_path = args.response.resolve()
    archive = args.archive.resolve()
    output = args.output.resolve()
    if not response_path.is_file():
        raise FileNotFoundError(response_path)
    if not archive.is_file():
        raise FileNotFoundError(archive)

    raw = response_path.read_text(encoding="utf-8-sig").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"FileDitch did not return JSON: {raw[:1000]!r}") from exc

    if data.get("success") is not True:
        raise RuntimeError(f"FileDitch upload was not successful: {data!r}")
    url = data.get("url")
    filename = data.get("filename")
    size = data.get("size")
    parsed = urlparse(url if isinstance(url, str) else "")
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(f"Invalid direct download URL: {url!r}")
    if not isinstance(filename, str) or not filename:
        raise RuntimeError(f"Invalid returned filename: {filename!r}")
    actual_size = archive.stat().st_size
    if not isinstance(size, int) or size != actual_size:
        raise RuntimeError(f"Uploaded size mismatch: response={size!r}, local={actual_size}")

    validated = {
        "success": True,
        "url": url,
        "filename": filename,
        "size_bytes": actual_size,
        "sha256": sha256(archive),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(validated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validated, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
