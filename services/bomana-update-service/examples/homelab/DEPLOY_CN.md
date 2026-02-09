# Bomana Update Service 部署（HomeLab 分离栈）

目标：将 Bomana 更新统计服务独立于 HomeLab 主 `docker-compose.yml` 运行，只通过主 Caddy 反向代理访问。

## 1. 准备目录

```bash
sudo mkdir -p /opt/stacks/bomana-update/app
sudo mkdir -p /opt/stacks/bomana-update/data
sudo mkdir -p /opt/stacks/bomana-update/data/manifests
```

## 2. 复制服务文件

从本仓库 `tools/update_service/` 复制以下文件到服务器：

- `Dockerfile` -> `/opt/stacks/bomana-update/app/Dockerfile`
- `requirements.txt` -> `/opt/stacks/bomana-update/app/requirements.txt`
- `server.py` -> `/opt/stacks/bomana-update/app/server.py`
- `examples/homelab/docker-compose.bomana-update.yml` -> `/opt/stacks/bomana-update/docker-compose.yml`

## 3. Manifest 策略（自动 + 可选兜底）

当前推荐 `MANIFEST_MODE=local_then_github`（优先本地兜底，GitHub 作为后备），无需手工更新 manifest：

- 优先读取本地 `/opt/stacks/bomana-update/data/manifests/manifest_<Channel>.json`
- 本地缺失或异常时自动读取 GitHub latest release 的 `manifest_<Channel>.json`
- GitHub 结果会缓存（默认 300 秒）

可选：你也可以放本地兜底文件到 `/opt/stacks/bomana-update/data/manifests/`：

- `manifest_Enhanced.json`
- `manifest_Standard.json`
- `manifest_Lite.json`

兜底文件要求：

- 推荐包含 `package_url`（GitHub Release 下载直链）；
- 若未提供 `package_url`，请至少包含 `app_version + package_asset`，并确保 `AUTO_GITHUB_PACKAGE_URL=1`（默认开启），服务会自动拼接 GitHub 下载地址。

## 4. 启动独立栈

```bash
cd /opt/stacks/bomana-update
sudo docker compose up -d --build
```

默认映射 `18080:8080`，由主 Caddy 通过 `host.docker.internal:18080` 反代访问。

## 5. 主 Caddy 接入

将 `examples/homelab/Caddyfile.bomana-update.snippet` 中的站点块加入你的 HomeLab 主 `Caddyfile`。

然后重载 Caddy：

```bash
cd /opt/HomeLab
sudo docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## 6. 验证

服务器本机：

```bash
curl -s http://127.0.0.1:18080/healthz
curl -s "http://127.0.0.1:18080/api/v1/version?channel=Enhanced"
curl -s "http://127.0.0.1:18080/api/v1/version?channel=Enhanced" | jq -r .source_name
```

域名链路：

```bash
curl -I https://bomanaupdate.ruikang.wang/healthz
curl -I "https://bomanaupdate.007985.xyz/healthz"
```

期望：

- 本机接口返回 `200`，并且 `source_name` 显示本地或 GitHub 来源
- 域名链路返回 `200`（不再出现 `301` 到其他域名，也不应出现 `525`）
