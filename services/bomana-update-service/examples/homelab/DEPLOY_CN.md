# Bomana Update Service 部署（分离栈示例）

目标：将 Bomana 更新服务独立运行，再通过现有反向代理统一对外暴露。

本文档只给出公开安全的示例，不包含私有域名、主机名或运行时数据。

## 1. 准备目录

```bash
sudo mkdir -p /opt/stacks/bomana-update/app
sudo mkdir -p /opt/stacks/bomana-update/data
sudo mkdir -p /opt/stacks/bomana-update/data/manifests
sudo mkdir -p /opt/stacks/bomana-update/data/downloads
```

## 2. 复制服务文件

从本仓库 `services/bomana-update-service/` 复制以下文件到服务器：

- `Dockerfile` -> `/opt/stacks/bomana-update/app/Dockerfile`
- `requirements.txt` -> `/opt/stacks/bomana-update/app/requirements.txt`
- `server.py` -> `/opt/stacks/bomana-update/app/server.py`
- `examples/homelab/docker-compose.bomana-update.yml` -> `/opt/stacks/bomana-update/docker-compose.yml`

## 3. 准备运行时数据

推荐使用本地 manifest + 同域下载分发：

- `MANIFEST_MODE=local`
- `STATS_ONLY_MODE=0`
- `DOWNLOAD_BASE_URL=https://update.example.com`

建议由发布流程自动同步这些文件：

- `/opt/stacks/bomana-update/data/manifests/manifest_Enhanced.json`
- `/opt/stacks/bomana-update/data/manifests/manifest_Standard.json`
- `/opt/stacks/bomana-update/data/manifests/manifest_Lite.json`
- `/opt/stacks/bomana-update/data/launcher_manifest.json`
- `/opt/stacks/bomana-update/data/downloads/Bomana_app_*.zip`
- `/opt/stacks/bomana-update/data/downloads/Bomana_launcher_v*.exe`

服务将对外提供：

- `GET /api/v1/version`
- `GET /api/v1/launcher`
- `GET /downloads/<asset>`

## 4. GitHub 回退（可选）

如果你暂时不想自托管所有包体，可以切换到：

- `MANIFEST_MODE=github_then_local`
- `AUTO_GITHUB_PACKAGE_URL=1`

这时服务会优先读取 GitHub latest release 的 manifest，本地文件作为兜底。

## 5. 启动服务

```bash
cd /opt/stacks/bomana-update
sudo docker compose up -d --build
```

示例 compose 只监听 `127.0.0.1:18080`，不直接对公网暴露。

## 6. 配置反向代理

将 `examples/homelab/Caddyfile.bomana-update.snippet` 里的站点块加入你的主 Caddyfile，并把 `update.example.com` 替换成你的真实域名。

服务需要转发的路径包括：

- `/healthz`
- `/api/*`
- `/downloads/*`

## 7. 验证

服务器本机：

```bash
curl -s http://127.0.0.1:18080/healthz
curl -s "http://127.0.0.1:18080/api/v1/version?channel=Enhanced"
curl -s "http://127.0.0.1:18080/api/v1/launcher"
curl -I "http://127.0.0.1:18080/downloads/Bomana_launcher_v1.2.0.exe"
```

域名链路：

```bash
curl -I https://update.example.com/healthz
curl -I "https://update.example.com/api/v1/version?channel=Enhanced"
```

期望结果：都返回 `200`，并且 `/downloads/*` 可以直接命中服务端静态文件。
