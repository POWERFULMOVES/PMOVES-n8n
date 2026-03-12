# PMOVES-n8n Runtime

## Purpose

`PMOVES-n8n` is the authoritative PMOVES.AI lane for:

- n8n runtime image overlay
- canonical workflow exports
- workflow import/export tooling
- PMOVES-specific operator documentation

This keeps runtime and workflow ownership together instead of splitting them across root compose files, ad-hoc scripts, and mirrored JSON exports.

## Source-of-truth layout

- `compose/n8n/Dockerfile`
- `workflows/*.json`
- `scripts/bootstrap_n8n_api.py`
- `scripts/n8n_flow_normalize.py`
- `scripts/import_repo_flows.py`
- `scripts/export_repo_flows.py`
- `scripts/sync_supabase_registry.py`

## Parent repo consumption

The parent `PMOVES.AI/pmoves` stack should:

- build the `n8n` service from `../PMOVES-n8n/compose/n8n/Dockerfile`
- mount `../PMOVES-n8n/workflows` into `/flows`
- run n8n with the dedicated `n8n-db` Postgres sidecar for production
- expose `make -C pmoves n8n-api-bootstrap`, `n8n-import-flows`, `n8n-activate-flows`, `n8n-sync-supabase-registry`, `n8n-bootstrap`, and `n8n-export-repo-flows`

## Import/update model

- Production/default:
  - bootstrap the owner account and API key with `scripts/bootstrap_n8n_api.py`
  - workflow definitions are updated in place via the n8n Public API
  - workflow activation uses `/api/v1/workflows/{id}/activate|deactivate`
  - live workflow state is synced into `pmoves_core.n8n_workflow_registry`
- Fallback: no valid API key
  - missing workflows are imported via n8n CLI
  - activation falls back to CLI publish/unpublish
  - existing workflows are not rewritten without API access

## Compatibility mirror

The parent repo may keep `pmoves/n8n/flows/` as a mirror for:

- legacy docs references
- UI/doc links
- staged transition work

But canonical edits should land in `PMOVES-n8n/workflows/` first.
