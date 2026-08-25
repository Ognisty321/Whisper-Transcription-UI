#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("input", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
text = args.input.read_text(encoding="utf-8", errors="replace")
decoder = json.JSONDecoder()
for index, character in enumerate(text):
    if character != "{":
        continue
    try:
        value, end = decoder.raw_decode(text[index:])
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict):
        args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        raise SystemExit(0)
raise SystemExit("No JSON object found in console output")
