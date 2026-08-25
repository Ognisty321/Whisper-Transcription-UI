#!/usr/bin/env python3
"""Generate a small deterministic PCM WAV for end-to-end decoder smoke tests."""

from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=float, default=2.0)
    args = parser.parse_args()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16_000
    frame_count = int(sample_rate * args.seconds)

    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            time_s = index / sample_rate
            carrier = math.sin(2.0 * math.pi * (220.0 + 110.0 * time_s) * time_s)
            envelope = 0.5 * (1.0 - math.cos(2.0 * math.pi * index / max(frame_count - 1, 1)))
            sample = int(9000.0 * carrier * envelope)
            frames.extend(struct.pack("<h", sample))
        stream.writeframes(frames)

    print(f"Generated {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
