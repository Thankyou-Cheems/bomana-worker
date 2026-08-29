# Final production snapshot provenance

This directory is the public-safe source snapshot copied from the stopped TencentCloudPublic `/opt/stacks/bomana-update` stack before its deletion. The copy was made on 2026-08-30 after `bomana-anonymous-metrics` had replaced the Python service and all Legacy Launcher/App delivery routes had been retired.

| Archived file | Former server path | SHA-256 |
|---|---|---|
| `app/server.py` | `/opt/stacks/bomana-update/app/server.py` | `177250efb1f555f844503339e900b1893028d33a046309a2146c05e0b6b529ab` |
| `app/requirements.txt` | `/opt/stacks/bomana-update/app/requirements.txt` | `4ad83c8db10eb4f396169bc4510da34458b0dce37adca713809b098bd33d51af` |
| `app/Dockerfile` | `/opt/stacks/bomana-update/app/Dockerfile` | `d1575622374c16216b3f39011ff0de4eedc5c431b705b10ead3c625cfb270510` |
| `docker-compose.yml` | `/opt/stacks/bomana-update/docker-compose.yml` | `75b61de223d52a586c568eb721df4fd092b32894a8b810ec9a651a7389de04f0` |
| `DEPLOY_CN.md` | `/opt/stacks/bomana-update/DEPLOY_CN.md` | `80190d58c8b8807d0ef6c759bf29e9e92c2c42cedfb7355dceebaa50172d1353` |
| `Caddyfile.bomana-update.snippet` | `/opt/stacks/bomana-update/Caddyfile.bomana-update.snippet` | `b9340930ffd307215a391542ef6c1891e5128fee32d4a69518446c245d1486e2` |

The local and server hashes were compared before this snapshot was staged. No hard-coded credential was found; `GITHUB_TOKEN` is only an optional environment lookup.

The following operational material is deliberately not archived in Git:

- SQLite statistics databases and per-installation daily tokens;
- App, Launcher, and Terrain ZIP/EXE/BTH release bytes;
- container images, logs, caches, incoming candidates, and rollback directories;
- credentials, environment values, and private host configuration.

The current signed Terrain object closure was migrated separately to `/opt/stacks/bomana-terrain`; the compatible statistics database remains owned by `/opt/stacks/bomana-analytics`.
