#!/usr/bin/env python3
"""Import or activate canonical PMOVES n8n workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from n8n_flow_normalize import _as_workflow_obj

DEFAULT_INACTIVE_FILENAMES = {
    "discord_voice_agent.json",
    "telegram_voice_agent.json",
    "finance_firefly_sync.json",
    "finance_monthly_to_cgp.json",
    "health_weekly_to_cgp.json",
}


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, check=check)


def docker_exec(container: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", container, *args], check=check)


def parse_cli_workflows(raw: str) -> dict[str, dict[str, str]]:
    workflows: dict[str, dict[str, str]] = {}
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) < 4:
            continue
        workflow_id = parts[2].strip()
        name = parts[3].split("{", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z0-9]+", workflow_id) and name:
            workflows[name] = {"id": workflow_id, "name": name}
    return workflows


def load_local_workflows(workflow_dir: Path) -> list[dict[str, Any]]:
    workflows: list[dict[str, Any]] = []
    for path in sorted(workflow_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        workflow = _as_workflow_obj(data)
        workflow["_filename"] = path.name
        workflows.append(workflow)
    return workflows


def api_request(base_url: str, api_key: str, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read().decode("utf-8")
        return json.loads(content) if content else None


def activate_workflows_via_api(
    base_url: str,
    api_key: str,
    api_workflows: dict[str, dict[str, Any]],
    local_workflows: list[dict[str, Any]],
    enable_voice_platforms: bool,
) -> list[str]:
    failures: list[str] = []
    for workflow in local_workflows:
        name = workflow["name"]
        remote = api_workflows.get(name)
        if not remote:
            failures.append(name)
            print(f"warning: workflow missing from API list during activation: {name}")
            continue
        workflow_id = remote["id"]
        filename = workflow["_filename"]
        should_publish = enable_voice_platforms or filename not in DEFAULT_INACTIVE_FILENAMES
        try:
            if should_publish:
                payload: dict[str, Any] = {}
                version_id = remote.get("versionId")
                if version_id:
                    payload["versionId"] = version_id
                api_request(base_url, api_key, "POST", f"/workflows/{workflow_id}/activate", payload)
                state = "published"
            else:
                api_request(base_url, api_key, "POST", f"/workflows/{workflow_id}/deactivate", {})
                state = "unpublished"
            print(f"{state}: {name} ({workflow_id})")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            failures.append(f"{name} ({workflow_id})")
            print(f"warning: API activation failed for {name} ({workflow_id}): {exc}")
    return failures


def try_list_via_api(base_url: str, api_key: str) -> dict[str, dict[str, Any]] | None:
    if not api_key:
        return None
    try:
        result = api_request(base_url, api_key, "GET", "/workflows?limit=250")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    items = result.get("data", []) if isinstance(result, dict) else []
    return {item["name"]: item for item in items if isinstance(item, dict) and item.get("name")}


def create_payload(local_workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": local_workflow["name"],
        "nodes": local_workflow["nodes"],
        "connections": local_workflow["connections"],
        "settings": local_workflow.get("settings") or {},
        "staticData": local_workflow.get("staticData"),
    }


def update_payload(local_workflow: dict[str, Any], remote_workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": local_workflow["name"],
        "nodes": local_workflow["nodes"],
        "connections": local_workflow["connections"],
        "settings": local_workflow.get("settings") or {},
        "staticData": local_workflow.get("staticData"),
    }


def activate_workflows(
    container: str,
    cli_workflows: dict[str, dict[str, str]],
    local_workflows: list[dict[str, Any]],
    enable_voice_platforms: bool,
) -> list[str]:
    failures: list[str] = []
    for workflow in local_workflows:
        name = workflow["name"]
        remote = cli_workflows.get(name)
        if not remote:
            continue
        workflow_id = remote["id"]
        filename = workflow["_filename"]
        should_publish = enable_voice_platforms or filename not in DEFAULT_INACTIVE_FILENAMES
        command = "publish:workflow" if should_publish else "unpublish:workflow"
        try:
            docker_exec(container, "n8n", command, f"--id={workflow_id}")
            state = "published" if should_publish else "unpublished"
        except subprocess.CalledProcessError:
            try:
                docker_exec(container, "n8n", "update:workflow", f"--id={workflow_id}", f"--active={'true' if should_publish else 'false'}")
                state = "activated via update:workflow" if should_publish else "deactivated via update:workflow"
            except subprocess.CalledProcessError:
                failures.append(f"{name} ({workflow_id})")
                print(f"warning: activation failed for {name} ({workflow_id})")
                continue
        print(f"{state}: {name} ({workflow_id})")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Import or activate canonical PMOVES n8n workflows.")
    parser.add_argument("--container", default=os.environ.get("N8N_CONTAINER", "pmoves-n8n"))
    parser.add_argument("--workflow-dir", type=Path, default=Path(__file__).resolve().parents[1] / "workflows")
    parser.add_argument("--container-workflow-dir", default="/flows")
    parser.add_argument("--n8n-api-url", default=os.environ.get("N8N_API_URL", "http://localhost:5678/api/v1"))
    parser.add_argument("--activate-only", action="store_true")
    parser.add_argument("--skip-activation", action="store_true")
    parser.add_argument("--voice-platforms", action="store_true")
    args = parser.parse_args()

    local_workflows = load_local_workflows(args.workflow_dir)
    cli_workflows = parse_cli_workflows(docker_exec(args.container, "n8n", "list:workflow").stdout)
    api_key = os.environ.get("N8N_API_KEY", "")
    api_workflows = try_list_via_api(args.n8n_api_url, api_key) if api_key else None

    if not args.activate_only:
        if api_workflows is not None:
            print("Using n8n Public API for workflow upserts.")
            for workflow in local_workflows:
                remote = api_workflows.get(workflow["name"])
                if remote:
                    remote_full = api_request(args.n8n_api_url, api_key, "GET", f"/workflows/{remote['id']}")
                    payload = update_payload(workflow, remote_full)
                    api_request(args.n8n_api_url, api_key, "PUT", f"/workflows/{remote['id']}", payload)
                    print(f"updated: {workflow['name']} ({remote['id']})")
                else:
                    created = api_request(args.n8n_api_url, api_key, "POST", "/workflows", create_payload(workflow))
                    created_id = created.get("id", "unknown") if isinstance(created, dict) else "unknown"
                    print(f"created: {workflow['name']} ({created_id})")
            cli_workflows = parse_cli_workflows(docker_exec(args.container, "n8n", "list:workflow").stdout)
            api_workflows = try_list_via_api(args.n8n_api_url, api_key)
        else:
            print("No valid N8N_API_KEY detected. Falling back to CLI import for missing workflows.")
            import_failures: list[str] = []
            for workflow in local_workflows:
                if workflow["name"] in cli_workflows:
                    print(f"skipped existing: {workflow['name']}")
                    continue
                docker_path = f"{args.container_workflow_dir.rstrip('/')}/{workflow['_filename']}"
                try:
                    docker_exec(args.container, "n8n", "import:workflow", f"--input={docker_path}")
                    print(f"imported: {workflow['name']}")
                except subprocess.CalledProcessError:
                    import_failures.append(workflow["name"])
                    print(f"warning: import failed for {workflow['name']}")
            cli_workflows = parse_cli_workflows(docker_exec(args.container, "n8n", "list:workflow").stdout)
            if import_failures:
                print("warning: some workflow imports failed via CLI; use a valid N8N_API_KEY for in-place upserts or clean the local n8n DB before retrying.")

    if args.skip_activation:
        return 0

    if api_workflows is not None:
        activation_failures = activate_workflows_via_api(
            args.n8n_api_url,
            api_key,
            api_workflows,
            local_workflows,
            args.voice_platforms,
        )
    else:
        activation_failures = activate_workflows(args.container, cli_workflows, local_workflows, args.voice_platforms)
    if activation_failures:
        if api_workflows is not None:
            print("warning: some workflows could not be toggled via the n8n Public API.")
        else:
            print("warning: some workflows could not be toggled because the local n8n DB has legacy/broken version records.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or exc.stdout or str(exc))
        raise
