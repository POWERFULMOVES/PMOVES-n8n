# PMOVES.AI Integration Guide for PMOVES-n8n

## Integration Overview

PMOVES-n8n is the authoritative PMOVES.AI fork lane for n8n runtime packaging, workflow canon, and operator tooling. It contains the canonical workflow catalog, the PMOVES n8n image overlay, and the import/export helpers used by the parent PMOVES.AI repo.

## Service Details

- **Name:** PMOVES n8n
- **Slug:** pmoves-n8n
- **Tier:** orchestration
- **Port:** 5678 (n8n server)
- **Health Check:** http://localhost:5678/healthz
- **NATS Enabled:** Implicit (via HTTP triggers to NATS-connected services)
- **GPU Enabled:** False

## Integration Points

### Workflow Catalog
| Workflow | Purpose |
|----------|---------|
| `echo_publisher.json` | Discord content publishing |
| `approval_poller.json` | Content approval pipeline |
| `discord_voice_agent.json` | Discord voice ingress |
| `voice_platform_router.json` | Shared voice routing |
| `health_weekly_to_cgp.json` | Weekly health reports to CGP |
| `finance_monthly_to_cgp.json` | Monthly finance reports to CGP |
| `firefly_sync_to_supabase.json` | Firefly III finance sync |
| `wger_sync_to_supabase.json` | wger health tracking sync |
| `yt_docs_sync_diff.json` | YouTube docs synchronization |
| `pmoves_echo_ingest.json` | Content ingestion orchestration |
| `pmoves_comfy_gen.json` | ComfyUI generation trigger |
| `pmoves_content_approval.json` | Content approval workflow |

### Data Flow
```
n8n Workflows → Supabase (health/wealth data)
              → Discord (notifications/publishing)
              → ComfyUI (media generation)
              → PMOVES.YT (YouTube sync)
              → CGP (geometry bus reports)
```

### Deployment
```bash
# Parent repo operator path
make -C pmoves up-n8n
make -C pmoves n8n-import-flows
make -C pmoves n8n-activate-flows

# Direct submodule path
python scripts/import_repo_flows.py --container pmoves-n8n --workflow-dir workflows
python scripts/export_repo_flows.py --container pmoves-n8n --workflow-dir workflows
```

## Next Steps

### 1. Runtime ownership

- Canonical workflows: `workflows/*.json`
- Runtime image overlay: `compose/n8n/Dockerfile`
- Import helper: `scripts/import_repo_flows.py`
- Export helper: `scripts/export_repo_flows.py`
- Runtime docs: `docs/RUNTIME.md`

The parent repo keeps `pmoves/n8n/flows/` as a compatibility mirror, but canonical edits should land here first.

### 2. Customize Environment Variables

- `N8N_API_KEY` - n8n API access key
- `N8N_API_URL` - n8n server URL (default: http://localhost:5678)
- See `pmoves/.env.example` for full list

### 3. Test Integration

```bash
# Verify n8n server
curl http://localhost:5678/healthz

# List workflows
curl -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows

# Verify environment
docker compose exec n8n env | grep PMOVES
```

## Files Created

- `compose/n8n/Dockerfile` - PMOVES n8n image overlay
- `docs/RUNTIME.md` - runtime and operator notes
- `scripts/import_repo_flows.py` - canonical import/update path
- `scripts/export_repo_flows.py` - canonical export path
- `scripts/n8n_flow_normalize.py` - workflow sanitation helper
- `PMOVES.AI_INTEGRATION.md` - this integration guide

## Support

For questions or issues, see the PMOVES.AI documentation.
