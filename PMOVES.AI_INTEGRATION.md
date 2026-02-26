# PMOVES.AI Integration Guide for n8n Workflows

## Integration Overview

PMOVES-n8n contains 11 workflow definitions for automating cross-service orchestration within PMOVES.AI. Workflows handle content publishing, approval pipelines, health/wealth data sync, YouTube documentation, and media generation triggers.

## Service Details

- **Name:** n8n Workflow Automation
- **Slug:** n8n
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
# Bulk import workflows
pmoves/scripts/n8n-import-flows.sh

# Import single workflow
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -d @workflows/echo_publisher.json
```

## Next Steps

### 1. Customize Environment Variables

- `N8N_API_KEY` - n8n API access key
- `N8N_API_URL` - n8n server URL (default: http://localhost:5678)
- See `pmoves/.env.example` for full list

### 2. Test Integration

```bash
# Verify n8n server
curl http://localhost:5678/healthz

# List workflows
curl -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows

# Verify environment
docker compose exec n8n env | grep PMOVES
```

## Files Created

- `PMOVES.AI_INTEGRATION.md` - This integration guide

## Support

For questions or issues, see the PMOVES.AI documentation.
