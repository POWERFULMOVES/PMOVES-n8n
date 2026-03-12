#!/usr/bin/env python3
"""Export live n8n workflows back into the canonical PMOVES repo layout."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from n8n_flow_normalize import normalize_file


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)


def docker_exec(container: str, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", container, *args])


def parse_cli_workflows(raw: str) -> list[tuple[str, str]]:
    workflows: list[tuple[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) < 4:
            continue
        workflow_id = parts[2].strip()
        name = parts[3].split("{", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z0-9]+", workflow_id) and name:
            workflows.append((workflow_id, name))
    return workflows


def workflow_name_map(workflow_dir: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for path in workflow_dir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        src = data[0] if isinstance(data, list) and data else data
        name = src.get("name") if isinstance(src, dict) else None
        if name:
            mapping[name] = path
    return mapping


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"{slug or 'workflow'}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export live n8n workflows into repo JSON files.")
    parser.add_argument("--container", default=os.environ.get("N8N_CONTAINER", "pmoves-n8n"))
    parser.add_argument("--workflow-dir", type=Path, default=Path(__file__).resolve().parents[1] / "workflows")
    args = parser.parse_args()

    args.workflow_dir.mkdir(parents=True, exist_ok=True)
    existing_names = workflow_name_map(args.workflow_dir)
    live_workflows = parse_cli_workflows(docker_exec(args.container, "n8n", "list:workflow").stdout)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        for workflow_id, workflow_name in live_workflows:
            remote_path = f"/tmp/pmoves-export-{workflow_id}.json"
            docker_exec(
                args.container,
                "sh",
                "-lc",
                f"rm -f {remote_path} && n8n export:workflow --id={workflow_id} --output={remote_path}",
            )
            local_temp = temp_root / f"{workflow_id}.json"
            run(["docker", "cp", f"{args.container}:{remote_path}", str(local_temp)])
            target = existing_names.get(workflow_name, args.workflow_dir / slugify(workflow_name))
            shutil.copy2(local_temp, target)
            normalize_file(target)
            print(f"exported: {workflow_name} -> {target.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
