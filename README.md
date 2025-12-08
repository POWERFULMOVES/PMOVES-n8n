# PMOVES-n8n

n8n workflow automations for the PMOVES.AI platform.

## Workflows

| Workflow | Description |
|----------|-------------|
| `echo_publisher.json` | Discord echo publishing |
| `approval_poller.json` | Content approval polling |
| `debug_cron.json` | Debug/test cron job |
| `health_weekly_to_cgp.json` | Weekly health report to CGP |
| `finance_monthly_to_cgp.json` | Monthly finance report to CGP |
| `firefly_sync_to_supabase.json` | Firefly III sync to Supabase |
| `wger_sync_to_supabase.json` | Wger health sync to Supabase |
| `yt_docs_sync_diff.json` | YouTube docs sync diff |
| `pmoves_echo_ingest.json` | PMOVES echo ingestion |
| `pmoves_comfy_gen.json` | ComfyUI generation trigger |
| `pmoves_content_approval.json` | Content approval workflow |

## Usage

Import workflows via n8n API:
```bash
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Authorization: Bearer $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/echo_publisher.json
```

Or use the bulk import script:
```bash
./pmoves/scripts/n8n-import-flows.sh
```

## Environment Variables

See `pmoves/.env.example` for required environment variables.

## License

MIT
