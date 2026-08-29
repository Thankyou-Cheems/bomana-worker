# Bomana Update Service 部署（HomeLab 分离栈）

目标：将 Bomana 更新统计服务独立于 HomeLab 主 `docker-compose.yml` 运行，只通过主 Caddy 反向代理访问。

## 0. 当前线上架构

当前生产链路如下：

```text
Bomana 启动器
  -> https://bomanaupdate.ruikang.wang
  -> Tencent EdgeOne
  -> HomeLab Caddy 容器
  -> homelab_web Docker 内网
  -> bomana-update:8080
```

关键约束：

- `bomana-update` 是独立 Compose 栈，但必须加入主 HomeLab 的 `homelab_web` 外部网络。
- `bomana-update` 不直接暴露宿主机端口；不要再依赖 `127.0.0.1:18080` 或 `host.docker.internal:18080`。
- Caddy 直接反代 `bomana-update:8080`。
- 站点块必须同时声明 `http://bomanaupdate.ruikang.wang, https://bomanaupdate.ruikang.wang`。
- EdgeOne 当前会使用 HTTP 回源；如果 Caddy 只声明 HTTPS 站点，EdgeOne 回源会拿到 `308`，启动器 API 可能无法正确工作。
- Caddy 仍会为 HTTPS 直连申请和维护 Let’s Encrypt 证书。

接口与缓存职责：

- `/api/v1/launcher`：启动器更新检查，动态返回，必须 `no-store`。
- `/api/v1/version?channel=Standard|Lite|Enhanced`：应用更新检查，动态返回，必须 `no-store`。
- `/downloads/*`：版本化下载文件，可 CDN 长缓存。
- `/launcher_manifest.json`、`/manifests/*`：旧启动器/旧工具兼容路径，必须保留，建议 `no-store`。

发布时请同步：

- `/opt/stacks/bomana-update/data/launcher_manifest.json`
- `/opt/stacks/bomana-update/data/downloads/launcher_manifest.json`

这两个文件应保持一致，避免旧路径继续返回旧启动器版本。

## 1. 准备目录

```bash
sudo mkdir -p /opt/stacks/bomana-update/app
sudo mkdir -p /opt/stacks/bomana-update/data
sudo mkdir -p /opt/stacks/bomana-update/data/manifests
sudo mkdir -p /opt/stacks/bomana-update/data/downloads
```

## 2. 复制服务文件

从本仓库 `tools/update_service/` 复制以下文件到服务器：

- `Dockerfile` -> `/opt/stacks/bomana-update/app/Dockerfile`
- `requirements.txt` -> `/opt/stacks/bomana-update/app/requirements.txt`
- `server.py` -> `/opt/stacks/bomana-update/app/server.py`
- `examples/homelab/docker-compose.bomana-update.yml` -> `/opt/stacks/bomana-update/docker-compose.yml`

## 3. Manifest / 下载包策略

当前推荐配置是本地 manifest + 同域 `/downloads` 静态分发：

- `MANIFEST_MODE=local`
- `STATS_ONLY_MODE=0`
- `DOWNLOAD_BASE_URL=https://bomanaupdate.ruikang.wang`

需要由发布流程同步这些文件到服务器：

- `/opt/stacks/bomana-update/data/manifests/manifest_Enhanced.json`
- `/opt/stacks/bomana-update/data/manifests/manifest_Standard.json`
- `/opt/stacks/bomana-update/data/manifests/manifest_Lite.json`
- `/opt/stacks/bomana-update/data/launcher_manifest.json`
- `/opt/stacks/bomana-update/data/downloads/Bomana_app_*.zip`
- `/opt/stacks/bomana-update/data/downloads/Bomana_launcher_v*.exe`

服务会通过这些接口/路径对外提供：

- `GET /api/v1/version`：返回应用版本信息与包地址
- `GET /api/v1/launcher`：返回启动器版本信息与包地址
- `GET /downloads/<asset>`：直接下载应用包 / 启动器包

缓存策略约定：

- `/downloads/*`：应允许 CDN 长缓存（推荐 `public, max-age=31536000, immutable`），因为文件名已带版本号
- `/api/v1/*`：保持 `no-store`，避免版本查询结果被 CDN 陈旧缓存

## 4. GitHub 自动兜底（可选）

默认 `MANIFEST_MODE=github_then_local`，无需手工更新 manifest：

- 服务会自动读取 GitHub latest release 的 `manifest_<Channel>.json`
- 并缓存结果（默认 300 秒）

可选：你也可以放本地兜底文件到 `/opt/stacks/bomana-update/data/manifests/`：

- `manifest_Enhanced.json`
- `manifest_Standard.json`
- `manifest_Lite.json`

兜底文件要求：

- 推荐包含 `package_url`（GitHub Release 下载直链）；
- 若未提供 `package_url`，请至少包含 `app_version + package_asset`，并确保 `AUTO_GITHUB_PACKAGE_URL=1`（默认开启），服务会自动拼接 GitHub 下载地址。

如果需要让启动器元数据也走 GitHub 回退，可准备 `launcher_manifest.json`，字段示例：

```json
{
  "launcher_version": "1.2.0",
  "launcher_asset": "Bomana_launcher_v1.2.0.exe",
  "launcher_sha256": "..."
}
```

## 5. 启动独立栈

```bash
cd /opt/stacks/bomana-update
sudo docker compose up -d --build
```

本服务不发布宿主机端口，依靠 `homelab_web` 内网给 Caddy 访问。`docker-compose.yml` 应包含：

```yaml
services:
  bomana-update:
    networks:
      - web

networks:
  web:
    external: true
    name: homelab_web
```

如果看到 `ports: "127.0.0.1:18080:8080"`，说明配置回到了旧架构，需要移除。

## 6. 主 Caddy 接入

将 `examples/homelab/Caddyfile.bomana-update.snippet` 中的站点块加入你的 HomeLab 主 `Caddyfile`。

当前线上站点块要点：

```caddyfile
http://bomanaupdate.ruikang.wang, https://bomanaupdate.ruikang.wang {
  @launcher_json path /launcher_manifest.json /downloads/launcher_manifest.json
  handle @launcher_json {
    root * /opt/stacks/bomana-update/data
    header Cache-Control "no-store, no-cache, must-revalidate, private"
    file_server
  }

  @manifests path /manifests/*
  handle @manifests {
    root * /opt/stacks/bomana-update/data
    header Cache-Control "no-store, no-cache, must-revalidate, private"
    file_server
  }

  @downloads path /downloads/*
  handle @downloads {
    root * /opt/stacks/bomana-update/data
    header Cache-Control "public, max-age=31536000, immutable"
    file_server
  }

  handle {
    reverse_proxy bomana-update:8080
  }
}
```

不要把 `bomanaupdate.ruikang.wang` 写成仅 HTTPS 站点；EdgeOne HTTP 回源会触发 Caddy 自动 HTTP->HTTPS 跳转，导致 API 返回 `308`。

然后重载 Caddy：

```bash
cd /opt
sudo docker compose up -d --no-deps --force-recreate caddy
sudo docker exec caddy caddy validate --config /etc/caddy/Caddyfile
```

说明：如果用 `perl -pi` 等方式改了宿主机上的单文件 bind mount，容器内可能仍指向旧 inode；此时只 reload 不一定生效，直接 `--force-recreate caddy` 更稳。

## 7. 验证

服务器本机：

```bash
curl -s -H "Host: bomanaupdate.ruikang.wang" http://127.0.0.1/api/v1/launcher
curl -s "https://bomanaupdate.ruikang.wang/api/v1/version?channel=Standard&launcher_version=2.0.0"
curl -s "https://bomanaupdate.ruikang.wang/api/v1/version?channel=Lite&launcher_version=2.0.0"
curl -s "https://bomanaupdate.ruikang.wang/api/v1/version?channel=Enhanced&launcher_version=2.0.0"
curl -I "https://bomanaupdate.ruikang.wang/downloads/Bomana_launcher_v2.0.0.exe"
curl -I "https://bomanaupdate.ruikang.wang/downloads/Bomana_app_Standard_v6.14.4.zip"
```

域名链路：

```bash
curl -I https://bomanaupdate.ruikang.wang/healthz
curl -I https://bomanaupdate.ruikang.wang/launcher_manifest.json
curl -I https://bomanaupdate.ruikang.wang/manifests/manifest_Standard.json
```

期望：

- API 和兼容 JSON 路径返回 `200`，不应返回 `308`。
- 下载路径返回 `200`，并带有长期缓存头。
- `docker ps` 中 `caddy` 与 `bomana-update` 都应为 `healthy`。
