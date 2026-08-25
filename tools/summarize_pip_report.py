#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("report", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
report = json.loads(args.report.read_text(encoding="utf-8"))
rows = []
for item in report.get("install", []):
    metadata = item.get("metadata", {})
    rows.append(
        (
            metadata.get("name"),
            metadata.get("version"),
            item.get("download_info", {}).get("url"),
        )
    )
rows.sort(key=lambda row: (str(row[0]).lower(), str(row[1])))
args.output.write_text(
    "name\tversion\turl\n"
    + "\n".join("\t".join(str(value or "") for value in row) for row in rows)
    + "\n",
    encoding="utf-8",
)
print(f"resolved_distributions={len(rows)}")
