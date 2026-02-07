import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel


MANIFEST_DIR = Path(os.environ.get("MANIFEST_DIR", "/data/manifests"))
DB_PATH = Path(os.environ.get("DB_PATH", "/data/stats.db"))
DOWNLOAD_BASE_URL = os.environ.get("DOWNLOAD_BASE_URL", "").strip().rstrip("/")
SOURCE_NAME = os.environ.get("SOURCE_NAME", "TencentCloud")
ALLOWED_CHANNELS = {"Enhanced", "Standard", "Lite"}
STATS_ONLY_MODE = os.environ.get("STATS_ONLY_MODE", "1").strip().lower() not in {"0", "false", "off", "no"}
MANIFEST_MODE = os.environ.get("MANIFEST_MODE", "github_then_local").strip().lower()
GITHUB_REPO_OWNER = os.environ.get("GITHUB_REPO_OWNER", "Thankyou-Cheems").strip()
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO_NAME", "Bomana").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_CACHE_TTL_SEC = max(30, int(os.environ.get("GITHUB_CACHE_TTL_SEC", "300").strip() or "300"))
HTTP_TIMEOUT_SEC = max(2.0, float(os.environ.get("HTTP_TIMEOUT_SEC", "8").strip() or "8"))
UA = "BomanaUpdateService/1.0"

app = FastAPI(title="Bomana Update Service", version="1.0.0")
_DB_LOCK = threading.Lock()
_MANIFEST_CACHE_LOCK = threading.Lock()
_MANIFEST_CACHE: Dict[str, Dict[str, Any]] = {}


class EventPayload(BaseModel):
    event: str
    event_time_utc: Optional[str] = None
    channel: Optional[str] = ""
    launcher_version: Optional[str] = ""
    app_version: Optional[str] = ""
    local_version: Optional[str] = ""
    device_id: Optional[str] = ""
    install_id: Optional[str] = ""
    update_ok: Optional[bool] = None
    update_source: Optional[str] = ""
    update_error: Optional[str] = ""


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day_from_iso(ts: str) -> str:
    if not ts:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _db_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _DB_LOCK:
        conn = _db_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_time_utc TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    event TEXT NOT NULL,
                    channel TEXT,
                    launcher_version TEXT,
                    app_version TEXT,
                    local_version TEXT,
                    device_id TEXT,
                    install_id TEXT,
                    update_ok INTEGER,
                    update_source TEXT,
                    update_error TEXT,
                    ip TEXT,
                    user_agent TEXT,
                    payload_json TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_day ON events(day_utc)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event ON events(event)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_day_event_channel ON events(day_utc, event, channel)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_day_device ON events(day_utc, device_id)")
            conn.commit()
        finally:
            conn.close()


def _request_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


def _http_get_json(url: str) -> Dict[str, Any]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json, application/json, */*",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
        raw = resp.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _find_asset(assets: list, name: str) -> Optional[Dict[str, Any]]:
    for a in assets:
        if str(a.get("name", "")).strip().lower() == name.lower():
            return a
    return None


def _build_manifest_result(
    data: Dict[str, Any],
    source_name: str,
    release_assets: Optional[list] = None,
) -> Dict[str, Any]:
    app_version = str(data.get("app_version", "")).strip()
    package_url = str(data.get("package_url", "")).strip()
    package_asset = str(data.get("package_asset", "")).strip()
    package_sha256 = str(data.get("package_sha256", "")).strip()
    entrypoint = str(data.get("entrypoint", "Bomana.pyw")).strip() or "Bomana.pyw"

    if not app_version:
        raise HTTPException(status_code=500, detail="manifest missing required fields")

    if not package_url and package_asset and release_assets:
        asset = _find_asset(release_assets, package_asset)
        if asset:
            package_url = str(asset.get("browser_download_url", "")).strip()

    # Stats-only mode: do not serve downloadable files from this server unless explicit URL is provided.
    if STATS_ONLY_MODE:
        if not package_url:
            raise HTTPException(status_code=500, detail="STATS_ONLY_MODE requires manifest.package_url")
    else:
        # Compatibility mode:
        # 1) explicit package_url in manifest
        # 2) build from DOWNLOAD_BASE_URL + package_asset (self-hosted downloads)
        if not package_url:
            if not package_asset:
                raise HTTPException(status_code=500, detail="manifest missing package_url/package_asset")
            if not DOWNLOAD_BASE_URL:
                raise HTTPException(status_code=500, detail="DOWNLOAD_BASE_URL is empty and manifest.package_url is not set")
            package_url = f"{DOWNLOAD_BASE_URL}/downloads/{package_asset}"

    return {
        "app_version": app_version,
        "package_url": package_url,
        "package_sha256": package_sha256,
        "entrypoint": entrypoint,
        "source_name": source_name,
    }


def _load_manifest_from_local(channel: str) -> Dict[str, Any]:
    path = MANIFEST_DIR / f"manifest_{channel}.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"manifest not found: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"manifest parse error: {e}")
    return _build_manifest_result(data, source_name=SOURCE_NAME)


def _load_manifest_from_github(channel: str) -> Dict[str, Any]:
    now = time.time()
    cache_key = f"github:{channel}"
    with _MANIFEST_CACHE_LOCK:
        cached = _MANIFEST_CACHE.get(cache_key)
        if cached and (now - float(cached.get("ts", 0.0))) < GITHUB_CACHE_TTL_SEC:
            return dict(cached["value"])

    release_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
    try:
        release = _http_get_json(release_url)
    except HTTPError as e:
        raise HTTPException(status_code=502, detail=f"github release api http error: {e.code}")
    except URLError as e:
        raise HTTPException(status_code=502, detail=f"github release api unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"github release api parse error: {e}")

    assets = release.get("assets", []) if isinstance(release, dict) else []
    manifest_name = f"manifest_{channel}.json"
    manifest_asset = _find_asset(assets, manifest_name)
    if not manifest_asset:
        raise HTTPException(status_code=503, detail=f"github latest release missing {manifest_name}")

    manifest_url = str(manifest_asset.get("browser_download_url", "")).strip()
    if not manifest_url:
        raise HTTPException(status_code=503, detail=f"github manifest url invalid: {manifest_name}")

    try:
        manifest_data = _http_get_json(manifest_url)
    except HTTPError as e:
        raise HTTPException(status_code=502, detail=f"github manifest http error: {e.code}")
    except URLError as e:
        raise HTTPException(status_code=502, detail=f"github manifest unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"github manifest parse error: {e}")

    tag = str(release.get("tag_name", "latest")).strip() or "latest"
    result = _build_manifest_result(
        manifest_data,
        source_name=f"{SOURCE_NAME} (GitHub:{tag})",
        release_assets=assets,
    )

    with _MANIFEST_CACHE_LOCK:
        _MANIFEST_CACHE[cache_key] = {"ts": now, "value": dict(result)}
    return result


def _load_manifest(channel: str) -> Dict[str, Any]:
    if channel not in ALLOWED_CHANNELS:
        raise HTTPException(status_code=400, detail=f"unsupported channel: {channel}")

    mode = MANIFEST_MODE
    if mode == "local":
        return _load_manifest_from_local(channel)
    if mode == "github":
        return _load_manifest_from_github(channel)
    if mode == "local_then_github":
        try:
            return _load_manifest_from_local(channel)
        except Exception:
            return _load_manifest_from_github(channel)
    if mode == "github_then_local":
        try:
            return _load_manifest_from_github(channel)
        except Exception:
            return _load_manifest_from_local(channel)

    # unknown mode -> safe default
    try:
        return _load_manifest_from_github(channel)
    except Exception:
        return _load_manifest_from_local(channel)


def _insert_event(request: Request, payload: Dict[str, Any]) -> None:
    event_time = str(payload.get("event_time_utc", "")).strip() or _now_utc_iso()
    day_utc = _day_from_iso(event_time)
    row = {
        "event_time_utc": event_time,
        "day_utc": day_utc,
        "event": str(payload.get("event", "")).strip(),
        "channel": str(payload.get("channel", "")).strip(),
        "launcher_version": str(payload.get("launcher_version", "")).strip(),
        "app_version": str(payload.get("app_version", "")).strip(),
        "local_version": str(payload.get("local_version", "")).strip(),
        "device_id": str(payload.get("device_id", "")).strip(),
        "install_id": str(payload.get("install_id", "")).strip(),
        "update_ok": payload.get("update_ok", None),
        "update_source": str(payload.get("update_source", "")).strip(),
        "update_error": str(payload.get("update_error", "")).strip(),
        "ip": _request_ip(request),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "payload_json": json.dumps(payload, ensure_ascii=False),
    }
    if not row["event"]:
        return

    with _DB_LOCK:
        conn = _db_conn()
        try:
            conn.execute(
                """
                INSERT INTO events (
                    event_time_utc, day_utc, event, channel, launcher_version, app_version, local_version,
                    device_id, install_id, update_ok, update_source, update_error, ip, user_agent, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["event_time_utc"],
                    row["day_utc"],
                    row["event"],
                    row["channel"],
                    row["launcher_version"],
                    row["app_version"],
                    row["local_version"],
                    row["device_id"],
                    row["install_id"],
                    (None if row["update_ok"] is None else (1 if bool(row["update_ok"]) else 0)),
                    row["update_source"],
                    row["update_error"],
                    row["ip"],
                    row["user_agent"],
                    row["payload_json"],
                ),
            )
            conn.commit()
        finally:
            conn.close()


@app.on_event("startup")
def _on_startup() -> None:
    _init_db()


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "time_utc": _now_utc_iso(),
    }


@app.get("/api/v1/version")
def version(
    request: Request,
    channel: str = Query(..., description="Enhanced | Standard | Lite"),
    launcher_version: str = Query("", description="launcher version"),
    local_version: str = Query("", description="local app version"),
    device_id: str = Query("", description="hashed machine id"),
    install_id: str = Query("", description="install id"),
) -> Dict[str, Any]:
    manifest = _load_manifest(channel)
    _insert_event(
        request,
        {
            "event": "version_check",
            "event_time_utc": _now_utc_iso(),
            "channel": channel,
            "launcher_version": launcher_version,
            "local_version": local_version,
            "device_id": device_id,
            "install_id": install_id,
            "app_version": manifest.get("app_version", ""),
        },
    )
    return manifest


@app.post("/api/v1/event")
def event(request: Request, payload: EventPayload) -> Dict[str, Any]:
    _insert_event(request, payload.model_dump())
    return {
        "ok": True,
        "time_utc": _now_utc_iso(),
    }


@app.get("/api/v1/stats/daily")
def stats_daily(
    date: str = Query("", description="UTC date, format YYYY-MM-DD; default: today"),
    channel: str = Query("", description="optional channel filter"),
) -> Dict[str, Any]:
    target_day = date.strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    where = ["day_utc = ?"]
    params = [target_day]
    if channel:
        where.append("channel = ?")
        params.append(channel)
    where_sql = " AND ".join(where)

    with _DB_LOCK:
        conn = _db_conn()
        try:
            total_events = conn.execute(f"SELECT COUNT(1) AS n FROM events WHERE {where_sql}", params).fetchone()["n"]
            startup_total = conn.execute(
                f"SELECT COUNT(1) AS n FROM events WHERE {where_sql} AND event='launcher_start'",
                params,
            ).fetchone()["n"]
            app_launch_total = conn.execute(
                f"SELECT COUNT(1) AS n FROM events WHERE {where_sql} AND event='app_launch'",
                params,
            ).fetchone()["n"]
            version_check_total = conn.execute(
                f"SELECT COUNT(1) AS n FROM events WHERE {where_sql} AND event='version_check'",
                params,
            ).fetchone()["n"]
            update_ok_total = conn.execute(
                f"SELECT COUNT(1) AS n FROM events WHERE {where_sql} AND event='update_result' AND update_ok=1",
                params,
            ).fetchone()["n"]
            unique_device_dau = conn.execute(
                f"SELECT COUNT(DISTINCT device_id) AS n FROM events WHERE {where_sql} AND event='version_check' AND device_id<>''",
                params,
            ).fetchone()["n"]
            unique_install_dau = conn.execute(
                f"SELECT COUNT(DISTINCT install_id) AS n FROM events WHERE {where_sql} AND event='version_check' AND install_id<>''",
                params,
            ).fetchone()["n"]
        finally:
            conn.close()

    return {
        "date_utc": target_day,
        "channel": channel or "ALL",
        "metrics": {
            "total_events": int(total_events),
            "launcher_start_total": int(startup_total),
            "app_launch_total": int(app_launch_total),
            "version_check_total": int(version_check_total),
            "update_ok_total": int(update_ok_total),
            "dau_unique_device": int(unique_device_dau),
            "dau_unique_install": int(unique_install_dau),
        },
    }
