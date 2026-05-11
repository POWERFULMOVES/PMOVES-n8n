# PMOVES-n8n

Authoritative PMOVES.AI fork lane for n8n runtime packaging, workflow canon, and operator tooling.

## What lives here

- `workflows/` is the canonical PMOVES workflow catalog.
- `compose/n8n/Dockerfile` is the canonical PMOVES n8n image overlay.
- `scripts/import_repo_flows.py` imports or updates the repo workflows into a live n8n instance.
- `scripts/export_repo_flows.py` exports a live n8n instance back into repo-tracked workflow JSON.
- `docs/RUNTIME.md` is the runtime and operator reference.

The parent `PMOVES.AI` repo now consumes this submodule as the n8n source of truth. The older `pmoves/n8n/flows/` path is retained there as a compatibility mirror for docs and existing operator habits.

## Workflow inventory

Current catalog includes creator, publishing, finance, health, media, and ops flows, including:

- `approval_poller.json`
- `echo_publisher.json`
- `discord_voice_agent.json`
- `voice_platform_router.json`
- `pmoves_channel_monitor.json`
- `pmoves_jellyfin_watcher.json`
- `github_runner_autoscaler.json`
- `yt_docs_sync_diff.json`

## Operator path

From the parent repo:

```bash
make -C pmoves up-n8n
make -C pmoves n8n-api-bootstrap
make -C pmoves n8n-import-flows
make -C pmoves n8n-activate-flows
make -C pmoves n8n-sync-supabase-registry
make -C pmoves n8n-bootstrap
```

Directly from this submodule:

```bash
python scripts/bootstrap_n8n_api.py --write-env ../pmoves/.env.local
python scripts/import_repo_flows.py --container pmoves-n8n --workflow-dir workflows
python scripts/import_repo_flows.py --container pmoves-n8n --workflow-dir workflows --activate-only
python scripts/sync_supabase_registry.py --workflow-dir workflows
python scripts/export_repo_flows.py --container pmoves-n8n --workflow-dir workflows
```

## Public API note

The n8n 2.x Public API is the production control plane for this fork lane.

- `scripts/bootstrap_n8n_api.py` creates or logs into the owner account and mints a fresh API key.
- `scripts/import_repo_flows.py` uses the Public API for workflow upserts and activation when `N8N_API_KEY` is valid.
- `scripts/sync_supabase_registry.py` mirrors live workflow state into `pmoves_core.n8n_workflow_registry` so PMOVES can track workflow status in Supabase.

The CLI import path remains only as a legacy fallback when no valid API key is available.

## License

MIT
