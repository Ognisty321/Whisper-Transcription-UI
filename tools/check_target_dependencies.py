#!/usr/bin/env python3
"""Validate installed distribution requirements in a standalone --target tree."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.is_dir():
        raise NotADirectoryError(target)

    distributions = list(importlib.metadata.distributions(path=[str(target)]))
    installed: dict[str, dict[str, Any]] = {}
    for distribution in distributions:
        name = distribution.metadata.get("Name")
        version = distribution.version
        if not name:
            continue
        installed[canonicalize_name(name)] = {
            "name": name,
            "version": version,
            "path": str(distribution._path),  # diagnostic only
        }

    environment = default_environment()
    environment.update(
        {
            "python_full_version": platform.python_version(),
            "python_version": ".".join(platform.python_version_tuple()[:2]),
            "sys_platform": sys.platform,
            "platform_machine": platform.machine(),
            "platform_system": platform.system(),
            "implementation_name": sys.implementation.name,
        }
    )

    failures: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    for distribution in distributions:
        owner = distribution.metadata.get("Name") or "<unknown>"
        owner_version = distribution.version
        for raw_requirement in distribution.requires or []:
            try:
                requirement = Requirement(raw_requirement)
            except InvalidRequirement as exc:
                failures.append(
                    {
                        "owner": owner,
                        "owner_version": owner_version,
                        "requirement": raw_requirement,
                        "reason": f"invalid requirement: {exc}",
                    }
                )
                continue
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            canonical = canonicalize_name(requirement.name)
            candidate = installed.get(canonical)
            status = {
                "owner": owner,
                "owner_version": owner_version,
                "requirement": str(requirement),
                "installed": candidate,
            }
            if candidate is None:
                status["reason"] = "missing distribution"
                failures.append(status)
            elif requirement.specifier and Version(candidate["version"]) not in requirement.specifier:
                status["reason"] = "version does not satisfy specifier"
                failures.append(status)
            else:
                checked.append(status)

    report = {
        "target": str(target),
        "python": sys.version,
        "distribution_count": len(installed),
        "checked_requirement_count": len(checked),
        "failure_count": len(failures),
        "installed": dict(sorted(installed.items())),
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "distribution_count": report["distribution_count"],
        "checked_requirement_count": report["checked_requirement_count"],
        "failure_count": report["failure_count"],
    }, indent=2))
    if failures:
        for failure in failures[:50]:
            print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
