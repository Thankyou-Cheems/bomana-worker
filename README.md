# bomana-worker (archived)

This repository preserves the retired Bomana update-service implementations. It is not a deployable current Bomana service.

The production Python `bomana-update` container was stopped on 2026-08-29. Current Bomana uses:

- static signed Terrain distribution owned by `Thankyou-Cheems/Bomana-Super-Bomb`;
- the bounded `bomana-anonymous-metrics` service for Anonymous Daily Active Signals and aggregate reads;
- the browser Launcher/App and Bridge release surfaces hosted by the product repository.

Legacy Launcher/App manifests, general event intake, Python package delivery, and the Cloudflare reverse proxy are retired. Their public URLs return `410 Gone` where compatibility requires an explicit retirement response.

## Archive layout

- `archive/production-20260829/`: exact public-safe source and deployment files copied from the final stopped TencentCloudPublic stack before server deletion.
- `archive/repository-main-20260628/`: the former default-branch FastAPI and Cloudflare Worker source as it existed before retirement.

Runtime databases, package archives, logs, caches, credentials, and private server configuration are intentionally excluded. See the production snapshot provenance file for exact hashes and custody details.
