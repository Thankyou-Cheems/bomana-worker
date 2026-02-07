# Bomana 更新统计服务（Docker + Caddy）

## 目标

当前采用“仅统计，不分发文件”模式：

- 启动器优先访问本服务获取版本元数据（默认自动从 GitHub latest release 拉取）
- 安装包下载地址直接指向 GitHub Release（不走腾讯云带宽）
- 服务端只承担轻量 API 请求和统计落库

## 接口

- `GET /api/v1/version`：返回版本信息与下载地址
- `POST /api/v1/event`：接收启动器/应用事件
- `GET /api/v1/stats/daily`：查看 DAU 与启动统计
- `GET /healthz`：健康检查

## Manifest 来源（默认自动）

默认配置 `MANIFEST_MODE=github_then_local`：

- 先从 GitHub latest release 读取 `manifest_<Channel>.json`
- GitHub 异常时再尝试本地 `data/manifests/manifest_<Channel>.json`
- 返回结果有缓存，默认 `GITHUB_CACHE_TTL_SEC=300`

本地 manifest 示例（作为兜底）：

```json
{
  "app_version": "6.7.0",
  "package_asset": "Bomana_app_Enhanced_v6.7.0.zip",
  "package_sha256": "...",
  "entrypoint": "Bomana.pyw",
  "package_url": "https://github.com/Thankyou-Cheems/Bomana/releases/download/v6.7.0/Bomana_app_Enhanced_v6.7.0.zip"
}
```

说明：

- 存在 `package_url` 时，服务直接返回该地址
- 此模式下无需在云服务器托管 `/downloads/*`
- 默认 `STATS_ONLY_MODE=1`，服务会强制要求 `package_url`

## 目录结构

```text
data/
├─ manifests/                # 可选：仅作为 github_then_local 的兜底
│  ├─ manifest_Enhanced.json
│  ├─ manifest_Standard.json
│  └─ manifest_Lite.json
└─ stats.db
```

## 快速部署

1. 检查 `examples/docker-compose.yml` 环境变量
   - `STATS_ONLY_MODE="1"`
   - `MANIFEST_MODE=github_then_local`
   - `GITHUB_REPO_OWNER` / `GITHUB_REPO_NAME`
2. 启动服务：

```bash
cd tools/update_service/examples
docker compose up -d --build
```

3. Caddy 按 `examples/Caddyfile` 配置反代（主要是 `/api/*` 与 `/healthz`）

## 验证

```bash
curl -s http://127.0.0.1:18080/healthz
curl -s "http://127.0.0.1:18080/api/v1/version?channel=Enhanced"
curl -s "http://127.0.0.1:18080/api/v1/stats/daily"
```

## 统计口径建议

- DAU：`version_check` 按 `device_id + UTC 日期` 去重
- 启动次数：`launcher_start` 总数
- 成功启动应用次数：`app_launch` 总数
