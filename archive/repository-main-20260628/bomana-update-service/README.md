# Bomana 更新服务

这是一个基于 FastAPI 的更新与统计服务，供 Bomana 启动器和应用访问。

公开仓库中的所有示例都使用占位域名 `update.example.com`，不包含任何私有部署信息。

## 当前能力

- `GET /healthz`：健康检查
- `GET /api/v1/version?channel=<Channel>`：返回应用版本元数据
- `GET /api/v1/launcher`：返回启动器版本元数据
- `GET /downloads/<asset>`：分发应用包和启动器包
- `POST /api/v1/event`：接收启动器/应用事件
- `GET /api/v1/stats/daily`：单日统计
- `GET /api/v1/stats/summary`：汇总统计
- `GET /api/v1/stats/daily/list`：按日历史列表

## 两种常见模式

### 1. 自托管分发

适合将应用包和启动器包都放在自己的服务器或 CDN 上。

推荐环境变量：

- `STATS_ONLY_MODE=0`
- `MANIFEST_MODE=local`
- `DOWNLOAD_BASE_URL=https://update.example.com`
- `SOURCE_NAME=SelfHosted`

需要准备的运行时文件：

```text
data/
├─ manifests/
│  ├─ manifest_Enhanced.json
│  ├─ manifest_Standard.json
│  └─ manifest_Lite.json
├─ downloads/
│  ├─ Bomana_app_Enhanced_vX.Y.Z.zip
│  └─ Bomana_launcher_vA.B.C.exe
├─ launcher_manifest.json
└─ stats.db
```

应用 manifest 示例：

```json
{
  "app_version": "6.8.0",
  "package_asset": "Bomana_app_Enhanced_v6.8.0.zip",
  "package_sha256": "...",
  "entrypoint": "Bomana.pyw"
}
```

启动器 manifest 示例：

```json
{
  "launcher_version": "1.2.0",
  "launcher_asset": "Bomana_launcher_v1.2.0.exe",
  "launcher_sha256": "..."
}
```

当未显式提供 `package_url` 或 `launcher_url` 时，服务会基于 `DOWNLOAD_BASE_URL` 生成同域下载地址。

### 2. GitHub 兜底

适合先用 GitHub Release 托管包体，再逐步迁移到自托管。

常用环境变量：

- `MANIFEST_MODE=github_then_local`
- `AUTO_GITHUB_PACKAGE_URL=1`
- `GITHUB_REPO_OWNER=Thankyou-Cheems`
- `GITHUB_REPO_NAME=Bomana`

行为：

- 优先读取 GitHub latest release 中的 `manifest_<Channel>.json`
- GitHub 不可用时回退到本地 `data/manifests/manifest_<Channel>.json`
- 返回值可直接携带 `package_url`
- 若没有 `package_url`，服务可按 GitHub Release 规则自动拼接

## 部署示例

- 单机部署：`examples/docker-compose.yml`
- 反向代理示例：`examples/Caddyfile`
- 分离栈示例：`examples/homelab/docker-compose.bomana-update.yml`
- 中文部署说明：`examples/homelab/DEPLOY_CN.md`

## 快速验证

```bash
curl -s http://127.0.0.1:18080/healthz
curl -s "http://127.0.0.1:18080/api/v1/version?channel=Enhanced"
curl -s "http://127.0.0.1:18080/api/v1/launcher"
curl -I "http://127.0.0.1:18080/downloads/Bomana_launcher_v1.2.0.exe"
```
