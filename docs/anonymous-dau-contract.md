# Anonymous Daily Active Contract

`POST /api/v1/telemetry/dau` is the single privacy-bounded daily-active input
shared by Lite, Standard, and Enhanced. It is separate from the legacy
`POST /api/v1/event` operational collector and never falls back to it.

## Request allowlist

The endpoint accepts a JSON object of at most 1 KiB with exactly these fields:

```json
{
  "schema_version": 1,
  "install_day_token": "64 lowercase hexadecimal characters",
  "channel": "Lite"
}
```

- `channel` is `Lite`, `Standard`, or `Enhanced`.
- The client keeps a random local installation secret and derives
  `install_day_token` as HMAC-SHA-256 over the UTC date. The token is not based
  on hardware, an account, a receipt, an IP address, or game data.
- The same launcher installation uses one daily token across edition changes,
  so it counts once overall per UTC day. Its first accepted channel is retained
  only for the per-channel breakdown.
- Query parameters and all additional JSON fields are rejected with a generic
  `400` response.

## Storage and history

The service accepts a `(UTC day, install_day_token)` once. Its first accepted
report increments the durable per-day/per-channel aggregate; repeats return
`202` with `duplicate: true` and do not increment it.

`dau_daily_signals` contains only UTC day, daily token, receipt time, and
channel. It is pruned to a rolling 30 UTC-day window at startup and on receipt.
`dau_daily_aggregates` contains only durable day/channel counts and is not
deleted by that cleanup. This endpoint never stores request IP, user agent,
arbitrary payload JSON, a cross-day identifier, or CheemsPay identity.

Aggregate values are exposed as:

- `GET /api/v1/stats/daily`: `metrics.anonymous_dau`;
- `GET /api/v1/stats/daily/list`: each day's `metrics.anonymous_dau`;
- `GET /api/v1/stats/summary`:
  `metrics.anonymous_active_installation_days`, the sum of daily counts over the
  selected period rather than a cross-day unique-person count.

## Client integration

Launcher 3.5.4 and later schedules the report after the user launches any
edition. Standalone Green Lite uses the same payload contract. Both calls are
best-effort, run outside the startup-critical path with a short timeout, and do
not retry through the legacy event endpoint.
