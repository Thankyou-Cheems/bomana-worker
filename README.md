# bomana-worker

Workers and service-side components used by Bomana.

## Repository Layout

- `src/index.js`: Cloudflare Worker entry.
- `wrangler.jsonc`: Worker configuration.
- `services/bomana-update-service/`: Dockerized update metadata + stats service (FastAPI).

## Bomana Update Service

Path: `services/bomana-update-service/`

Key files:

- `server.py`: API server (`/healthz`, `/api/v1/version`, `/api/v1/event`, `/api/v1/stats/daily`)
- `Dockerfile`: container image build
- `examples/docker-compose.yml`: standalone deployment example
- `examples/homelab/docker-compose.bomana-update.yml`: homelab split-stack example
- `examples/homelab/Caddyfile.bomana-update.snippet`: Caddy reverse proxy snippet
- `examples/homelab/DEPLOY_CN.md`: Chinese deployment guide

## Deploy (Update Service)

Use the guide at:

- `services/bomana-update-service/examples/homelab/DEPLOY_CN.md`

## Notes

- Update service is designed for metadata + telemetry/stats, not package file hosting by default.
- Package download URLs are expected to come from GitHub Release manifests.
