#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
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


def infer_top_levels(stage: Path, dist_info: Path) -> set[str]:
    top = dist_info / "top_level.txt"
    names: set[str] = set()
    if top.is_file():
        for line in top.read_text(encoding="utf-8", errors="replace").splitlines():
            name = line.strip()
            if name:
                names.add(name)
    record = dist_info / "RECORD"
    if record.is_file():
        try:
            rows = csv.reader(record.read_text(encoding="utf-8", errors="replace").splitlines())
            for row in rows:
                if not row:
                    continue
                path = row[0].replace("\\", "/")
                first = path.split("/", 1)[0]
                if not first or first.endswith(".dist-info") or first.endswith(".data"):
                    continue
                if first in {"bin", "Scripts"}:
                    continue
                if "." in first and not first.endswith((".py", ".pyc", ".pyd", ".dll")):
                    continue
                names.add(first)
        except Exception:
            pass
    return names


def remove_old_distribution(contents: Path, dist_name: str) -> list[str]:
    removed=[]
    nd=norm_dist(dist_name)
    for child in list(contents.iterdir()):
        if child.is_dir() and child.name.endswith((".dist-info", ".egg-info")):
            stem=child.name.rsplit(".dist-info",1)[0].rsplit(".egg-info",1)[0]
            # remove trailing version by comparing normalized prefix
            if norm_dist(stem).startswith(nd + "-") or norm_dist(stem)==nd:
                shutil.rmtree(child, ignore_errors=True); removed.append(child.name)
    return removed


def remove_top_level(contents: Path, top: str) -> list[str]:
    removed=[]
    candidates=[contents/top]
    p=Path(top)
    if p.suffix in {".py", ".pyc", ".pyd", ".dll"}:
        stem=p.stem
        candidates += [contents/(stem+".py"), contents/(stem+".pyc")]
    else:
        candidates += [contents/(top+".py"), contents/(top+".pyc")]
    seen=set()
    for c in candidates:
        try: key=c.resolve()
        except Exception: key=c
        if key in seen: continue
        seen.add(key)
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=False); removed.append(c.name)
        elif c.exists():
            c.unlink(); removed.append(c.name)
    return removed


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("stage", type=Path)
    ap.add_argument("contents", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args=ap.parse_args()
    stage=args.stage.resolve(); contents=args.contents.resolve()
    if not stage.is_dir(): raise NotADirectoryError(stage)
    if not contents.is_dir(): raise NotADirectoryError(contents)

    report={"stage":str(stage),"contents":str(contents),"distributions":[]}
    dist_infos=sorted(stage.glob("*.dist-info"), key=lambda p:p.name.lower())
    for di in dist_infos:
        dist=dist_name_from_metadata(di)
        tops=sorted(infer_top_levels(stage,di))
        entry={"distribution":dist,"dist_info":di.name,"top_levels":tops,"removed":[]}
        entry["removed"].extend(remove_old_distribution(contents,dist))
        for top in tops:
            # Never delete generic shared executable/data directories.
            if top in {"bin", "Scripts"}: continue
            entry["removed"].extend(remove_top_level(contents,top))
        report["distributions"].append(entry)

    # Copy the complete stage after removing the old package trees.
    for child in stage.iterdir():
        dst=contents/child.name
        if child.is_dir():
            shutil.copytree(child,dst,dirs_exist_ok=True)
        else:
            shutil.copy2(child,dst)

    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
