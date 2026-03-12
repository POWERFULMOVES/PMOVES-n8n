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
make -C pmoves n8n-import-flows
make -C pmoves n8n-activate-flows
```

Directly from this submodule:

```bash
python scripts/import_repo_flows.py --container pmoves-n8n --workflow-dir workflows
python scripts/import_repo_flows.py --container pmoves-n8n --workflow-dir workflows --activate-only
python scripts/export_repo_flows.py --container pmoves-n8n --workflow-dir workflows
```

## Public API note

The n8n 2.x Public API requires a valid API key created in the n8n UI. If `N8N_API_KEY` is present and valid, the import tool performs API-based updates. Without a valid key it falls back to CLI import for missing workflows and CLI publish/unpublish for activation.

## License

MIT
