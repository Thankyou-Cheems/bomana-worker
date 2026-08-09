# bomana-worker

Public service-side components used by Bomana.

This repository is intentionally public-safe:

- no secrets
- no private server addresses
- no runtime `data/` contents
- all example domains use `update.example.com`

## Repository Layout

- `src/index.js`: optional Cloudflare Worker reverse proxy
- `wrangler.jsonc`: Worker configuration
- `services/bomana-update-service/`: FastAPI update service

## Bomana Update Service

Path: `services/bomana-update-service/`

Current capabilities:

- `GET /api/v1/version`: public Lite/Standard app update manifest by channel
- `GET /api/v1/launcher`: launcher self-update manifest
- `GET /downloads/<asset>`: static file delivery for app and launcher packages
- `POST /api/v1/event`: legacy launcher/app operational events
- `POST /api/v1/telemetry/dau`: unified anonymous daily-active signal for every edition
- `GET /api/v1/stats/daily`, `GET /api/v1/stats/summary`, `GET /api/v1/stats/daily/list`
- `GET /healthz`: health check

The public service remains the locator for public App and Launcher packages: its
existing manifest responses carry the current `package_url` or `launcher_url`.
Enhanced entitlement and exact-resource grants stay with CheemsPay. For Enhanced
terrain, CheemsPay may return the current immutable object CDN base while the
private signed manifest and per-object integrity checks remain authoritative.
There is no separate public `/api/v1/distribution` control plane.

The service supports two deployment styles:

- self-hosted public downloads: local Lite/Standard manifests + same-origin `/downloads/*`
- GitHub fallback: use GitHub release manifests and package URLs when local files are unavailable

## Cloudflare Worker

`src/index.js` is a thin reverse proxy for edge routing. It reads `UPDATE_ORIGIN` from the Worker environment and forwards:

- `/healthz`
- `/api/*`
- `/downloads/*`

If you do not need an edge proxy, deploy the FastAPI service directly behind your own reverse proxy.

## Deployment

- Service docs: `services/bomana-update-service/README.md`
- Homelab example: `services/bomana-update-service/examples/homelab/DEPLOY_CN.md`
