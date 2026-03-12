#!/usr/bin/env python3
"""Sync n8n workflow state into the PMOVES Supabase registry."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_INACTIVE_FILENAMES = {
    "discord_voice_agent.json",
    "telegram_voice_agent.json",
    "finance_firefly_sync.json",
    "finance_monthly_to_cgp.json",
    "health_weekly_to_cgp.json",
}


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: Any | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read().decode("utf-8")
        return json.loads(content) if content else None


def load_local_workflows(workflow_dir: Path) -> dict[str, dict[str, Any]]:
    workflows: dict[str, dict[str, Any]] = {}
    for path in sorted(workflow_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        workflow = data[0] if isinstance(data, list) and data else data
        if not isinstance(workflow, dict) or not workflow.get("name"):
            continue
        workflows[str(workflow["name"])] = {
            "filename": path.name,
            "canonical_path": f"PMOVES-n8n/workflows/{path.name}",
            "target_active": path.name not in DEFAULT_INACTIVE_FILENAMES,
            "nodes_count": len(workflow.get("nodes") or []),
        }
    return workflows


def list_workflows(api_url: str, api_key: str) -> list[dict[str, Any]]:
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    result = request_json("GET", urllib.parse.urljoin(api_url.rstrip("/") + "/", "workflows?limit=250"), headers)
    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    raise RuntimeError("Unexpected n8n workflow list response")


def sync_supabase(
    supabase_rest_url: str,
    service_role_key: str,
    schema: str,
    records: list[dict[str, Any]],
) -> None:
    if not records:
        print("no n8n workflow records to sync")
        return
    url = supabase_rest_url.rstrip("/") + "/n8n_workflow_registry?on_conflict=workflow_id"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Accept-Profile": schema,
        "Content-Profile": schema,
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    request_json("POST", url, headers, records)


def detect_db_container() -> str:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    candidates = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() in {"pmoves-supabase-db-1", "supabase_db_pmoves"}
    ]
    if not candidates:
        raise RuntimeError("Could not detect a running Supabase DB container for n8n registry sync")
    return candidates[0]


def sync_via_psql(db_container: str, schema: str, records: list[dict[str, Any]]) -> None:
    payload = json.dumps(records).replace("'", "''")
    sql = f"""
with payload as (
    select jsonb_array_elements('{payload}'::jsonb) as doc
)
insert into {schema}.n8n_workflow_registry (
    workflow_id,
    workflow_name,
    canonical_filename,
    canonical_path,
    source_repo,
    source_submodule_path,
    target_active,
    is_active,
    version_id,
    active_version_id,
    project_id,
    nodes_count,
    tags,
    sync_meta,
    last_synced_at
)
select
    doc->>'workflow_id',
    doc->>'workflow_name',
    doc->>'canonical_filename',
    doc->>'canonical_path',
    coalesce(doc->>'source_repo', 'PMOVES-n8n'),
    coalesce(doc->>'source_submodule_path', 'PMOVES-n8n/workflows'),
    coalesce((doc->>'target_active')::boolean, false),
    coalesce((doc->>'is_active')::boolean, false),
    nullif(doc->>'version_id', '')::uuid,
    nullif(doc->>'active_version_id', '')::uuid,
    doc->>'project_id',
    coalesce((doc->>'nodes_count')::integer, 0),
    coalesce(doc->'tags', '[]'::jsonb),
    coalesce(doc->'sync_meta', '{{}}'::jsonb),
    timezone('utc', now())
from payload
on conflict (workflow_id) do update set
    workflow_name = excluded.workflow_name,
    canonical_filename = excluded.canonical_filename,
    canonical_path = excluded.canonical_path,
    source_repo = excluded.source_repo,
    source_submodule_path = excluded.source_submodule_path,
    target_active = excluded.target_active,
    is_active = excluded.is_active,
    version_id = excluded.version_id,
    active_version_id = excluded.active_version_id,
    project_id = excluded.project_id,
    nodes_count = excluded.nodes_count,
    tags = excluded.tags,
    sync_meta = excluded.sync_meta,
    last_synced_at = excluded.last_synced_at;
"""
    subprocess.run(
        ["docker", "exec", "-i", db_container, "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync live n8n workflows into Supabase tracking.")
    parser.add_argument("--workflow-dir", type=Path, default=Path(__file__).resolve().parents[1] / "workflows")
    parser.add_argument("--n8n-api-url", default=os.environ.get("N8N_API_URL", "http://localhost:5678/api/v1"))
    parser.add_argument("--supabase-rest-url", default=os.environ.get("SUPABASE_REST_URL") or os.environ.get("SUPA_REST_URL") or "http://127.0.0.1:65421/rest/v1")
    parser.add_argument("--supabase-schema", default=os.environ.get("SUPABASE_PROFILE") or "pmoves_core")
    parser.add_argument("--db-container", default=os.environ.get("SUPABASE_DB_CONTAINER", ""))
    args = parser.parse_args()

    n8n_api_key = os.environ.get("N8N_API_KEY", "").strip()
    if not n8n_api_key:
        raise RuntimeError("N8N_API_KEY is required for Supabase workflow registry sync")
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    )
    if not supabase_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for Supabase workflow registry sync")

    local_workflows = load_local_workflows(args.workflow_dir)
    remote_workflows = list_workflows(args.n8n_api_url, n8n_api_key)

    records: list[dict[str, Any]] = []
    for workflow in remote_workflows:
        name = str(workflow.get("name") or "").strip()
        if not name:
            continue
        local = local_workflows.get(name, {})
        records.append(
            {
                "workflow_id": str(workflow.get("id")),
                "workflow_name": name,
                "canonical_filename": local.get("filename"),
                "canonical_path": local.get("canonical_path"),
                "source_repo": "PMOVES-n8n",
                "source_submodule_path": "PMOVES-n8n/workflows",
                "target_active": bool(local.get("target_active", False)),
                "is_active": bool(workflow.get("active", False)),
                "version_id": workflow.get("versionId"),
                "active_version_id": workflow.get("activeVersionId"),
                "project_id": workflow.get("projectId"),
                "nodes_count": int(local.get("nodes_count", 0)),
                "tags": workflow.get("tags") or [],
                "sync_meta": {
                    "updatedAt": workflow.get("updatedAt"),
                    "createdAt": workflow.get("createdAt"),
                },
            }
        )

    try:
        sync_supabase(args.supabase_rest_url, supabase_key, args.supabase_schema, records)
    except urllib.error.URLError:
        db_container = args.db_container or detect_db_container()
        sync_via_psql(db_container, args.supabase_schema, records)
        print(f"supabase REST unavailable; synced via psql in container {db_container}")
    print(f"synced {len(records)} n8n workflow records into Supabase schema {args.supabase_schema}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(detail or str(exc))
