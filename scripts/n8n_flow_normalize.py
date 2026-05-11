#!/usr/bin/env python3
"""Normalize n8n workflow JSON into an importable PMOVES repo shape."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any


def _version_id(value: Any) -> str:
    try:
        if value:
            return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        pass
    return str(uuid.uuid4())


def _as_workflow_obj(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        if not data:
            raise ValueError("Empty workflow list")
        src = data[0]
    elif isinstance(data, dict):
        src = data
    else:
        raise TypeError(f"Unsupported JSON type: {type(data)}")

    if isinstance(src, dict) and "nodes" in src and "connections" in src and "id" in src and "name" not in src:
        name = src.get("id") or "Unnamed workflow"
        settings = src.get("settings") or {}
        meta = src.get("meta") or {}
        return {
            "name": name,
            "nodes": src.get("nodes") or [],
            "connections": src.get("connections") or {},
            "settings": settings,
            "staticData": src.get("staticData"),
            "active": False,
            "meta": meta,
            "pinData": None,
            "versionId": _version_id(None),
            "versionCounter": 1,
            "triggerCount": 0,
            "tags": [],
        }

    if isinstance(src, dict) and "workflowId" in src and "nodes" in src and "connections" in src:
        name = src.get("name") or src.get("id") or "Unnamed workflow"
        settings = src.get("settings") or {}
        meta = src.get("meta") or {}
        return {
            "name": name,
            "nodes": src.get("nodes") or [],
            "connections": src.get("connections") or {},
            "settings": settings,
            "staticData": src.get("staticData"),
            "active": False,
            "meta": meta,
            "pinData": None,
            "versionId": _version_id(None),
            "versionCounter": 1,
            "triggerCount": 0,
            "tags": [],
        }

    if isinstance(src, dict) and "name" in src and "nodes" in src and "connections" in src:
        return {
            "name": src.get("name") or "Unnamed workflow",
            "nodes": src.get("nodes") or [],
            "connections": src.get("connections") or {},
            "settings": src.get("settings") or {},
            "staticData": src.get("staticData"),
            "active": False,
            "meta": src.get("meta") or {},
            "pinData": src.get("pinData"),
            "versionId": _version_id(src.get("versionId")),
            "versionCounter": int(src.get("versionCounter") or 1),
            "triggerCount": int(src.get("triggerCount") or 0),
            "tags": [],
        }

    keys = sorted(src.keys()) if isinstance(src, dict) else str(type(src))
    raise ValueError(f"Unrecognized workflow JSON shape: {keys}")


def normalize_file(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = [_as_workflow_obj(data)]
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize n8n workflow JSON in place.")
    parser.add_argument("--file", type=Path, help="Single workflow JSON file to normalize")
    parser.add_argument("--inplace-dir", type=Path, help="Normalize all *.json files in a directory")
    args = parser.parse_args()

    if bool(args.file) == bool(args.inplace_dir):
        parser.error("Provide exactly one of --file or --inplace-dir")

    if args.file:
        normalize_file(args.file)
        return 0

    for workflow_file in sorted(args.inplace_dir.glob("*.json")):
        normalize_file(workflow_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
