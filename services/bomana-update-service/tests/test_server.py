import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"


def load_service_module():
    module_name = f"bomana_update_service_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Bomana update service")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class UpdateServiceHttpTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.service = load_service_module()
        self.service.MANIFEST_DIR = self.data_dir / "manifests"
        self.service.DOWNLOAD_DIR = self.data_dir / "downloads"
        self.service.LAUNCHER_MANIFEST_PATH = self.data_dir / "launcher_manifest.json"
        self.service.DB_PATH = self.data_dir / "stats.db"
        self.service.DOWNLOAD_BASE_URL = "https://update.example.com"
        self.service.MANIFEST_MODE = "local"
        self.service.STATS_ONLY_MODE = False
        self.client_context = TestClient(self.service.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def db_connection(self):
        return sqlite3.connect(self.service.DB_PATH)

    def test_version_response_forwards_signed_changelog_fields(self):
        self.write_json(
            self.service.MANIFEST_DIR / "manifest_Lite.json",
            {
                "schema_version": 2,
                "channel": "Lite",
                "app_version": "8.7.3",
                "package_asset": "Bomana_app_Lite_v8.7.3.zip",
                "package_sha256": "a" * 64,
                "changelog_asset": "CHANGELOG_Lite_v8.7.3.md",
                "changelog_sha256": "b" * 64,
                "manifest_signature": {
                    "algorithm": "Ed25519",
                    "key_id": "test-release-root",
                    "signature": "test-signature",
                },
            },
        )

        response = self.client.get("/api/v1/version?channel=Lite")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["changelog_asset"], "CHANGELOG_Lite_v8.7.3.md")
        self.assertEqual(payload["changelog_sha256"], "b" * 64)
        self.assertEqual(
            payload["changelog_url"],
            "https://update.example.com/downloads/CHANGELOG_Lite_v8.7.3.md",
        )
        self.assertEqual(payload["manifest_signature"]["signature"], "test-signature")

    def test_daily_active_is_unified_across_channels_and_exposed_in_history(self):
        payload = {
            "schema_version": 1,
            "install_day_token": "b" * 64,
            "channel": "Standard",
        }

        first = self.client.post("/api/v1/telemetry/dau", json=payload)
        second = self.client.post(
            "/api/v1/telemetry/dau",
            json={**payload, "channel": "Enhanced"},
        )

        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.json(), {"accepted": True, "duplicate": False})
        self.assertEqual(second.status_code, 202)
        self.assertEqual(second.json(), {"accepted": True, "duplicate": True})

        daily = self.client.get("/api/v1/stats/daily")
        standard_daily = self.client.get("/api/v1/stats/daily?channel=Standard")
        enhanced_daily = self.client.get("/api/v1/stats/daily?channel=Enhanced")
        history = self.client.get("/api/v1/stats/daily/list")
        summary = self.client.get("/api/v1/stats/summary")

        self.assertEqual(daily.json()["metrics"]["anonymous_dau"], 1)
        self.assertEqual(daily.json()["metrics"]["dau_unique_device"], 1)
        self.assertEqual(daily.json()["metrics"]["legacy_dau_unique_device"], 0)
        self.assertEqual(standard_daily.json()["metrics"]["anonymous_dau"], 1)
        self.assertEqual(enhanced_daily.json()["metrics"]["anonymous_dau"], 0)
        self.assertEqual(history.json()["total_days"], 1)
        self.assertEqual(
            history.json()["daily_stats"][0]["metrics"]["anonymous_dau"], 1
        )
        self.assertEqual(
            history.json()["daily_stats"][0]["metrics"]["dau_unique_device"], 1
        )
        self.assertEqual(
            summary.json()["metrics"]["anonymous_active_installation_days"],
            1,
        )

        with closing(self.db_connection()) as conn:
            raw_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(dau_daily_signals)")
            }
        self.assertEqual(
            raw_columns,
            {"day_utc", "install_day_token", "received_at_utc", "channel"},
        )

    def test_daily_active_allows_only_the_exact_bomana_web_cors_contract(self):
        headers = {
            "Origin": "https://bomana.ruikang.wang",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        preflight = self.client.options("/api/v1/telemetry/dau", headers=headers)
        self.assertEqual(preflight.status_code, 204)
        self.assertEqual(
            preflight.headers["access-control-allow-origin"],
            "https://bomana.ruikang.wang",
        )
        self.assertEqual(
            preflight.headers["access-control-allow-methods"], "POST, OPTIONS"
        )
        self.assertEqual(
            preflight.headers["access-control-allow-headers"], "Content-Type"
        )

        accepted = self.client.post(
            "/api/v1/telemetry/dau",
            headers={"Origin": "https://bomana.ruikang.wang"},
            json={
                "schema_version": 1,
                "install_day_token": "f" * 64,
                "channel": "Lite",
            },
        )
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(
            accepted.headers["access-control-allow-origin"],
            "https://bomana.ruikang.wang",
        )

        rejected = self.client.options(
            "/api/v1/telemetry/dau",
            headers={**headers, "Origin": "https://evil.example"},
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertNotIn("access-control-allow-origin", rejected.headers)
        unrelated = self.client.options("/api/v1/event", headers=headers)
        self.assertEqual(unrelated.status_code, 405)

    def test_daily_active_rejects_disallowed_data_without_persisting_it(self):
        response = self.client.post(
            "/api/v1/telemetry/dau",
            json={
                "schema_version": 1,
                "install_day_token": "c" * 64,
                "channel": "Lite",
                "device_id": "hardware-fingerprint",
                "receipt": "payment-receipt",
                "path": "/private/path",
            },
        )

        expected_error = {"detail": "invalid anonymous daily activity payload"}
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), expected_error)
        self.assertNotIn("hardware-fingerprint", response.text)
        self.assertNotIn("payment-receipt", response.text)
        with closing(self.db_connection()) as conn:
            raw_count = conn.execute(
                "SELECT COUNT(1) FROM dau_daily_signals"
            ).fetchone()[0]
            aggregate_count = conn.execute(
                "SELECT COUNT(1) FROM dau_daily_aggregates"
            ).fetchone()[0]
        self.assertEqual(raw_count, 0)
        self.assertEqual(aggregate_count, 0)

    def test_daily_active_prunes_raw_signals_but_keeps_historical_aggregates(self):
        old_day = (datetime.now(timezone.utc).date() - timedelta(days=31)).isoformat()
        with closing(self.db_connection()) as conn:
            conn.execute(
                "INSERT INTO dau_daily_signals "
                "(day_utc, install_day_token, received_at_utc, channel) "
                "VALUES (?, ?, ?, ?)",
                (old_day, "d" * 64, f"{old_day}T00:00:00Z", "Enhanced"),
            )
            conn.execute(
                "INSERT INTO dau_daily_aggregates "
                "(day_utc, channel, active_installations) VALUES (?, ?, ?)",
                (old_day, "Enhanced", 7),
            )
            conn.commit()

        response = self.client.post(
            "/api/v1/telemetry/dau",
            json={
                "schema_version": 1,
                "install_day_token": "e" * 64,
                "channel": "Enhanced",
            },
        )
        old_history = self.client.get(
            f"/api/v1/stats/daily/list?start_date={old_day}&end_date={old_day}"
        )
        summary = self.client.get("/api/v1/stats/summary")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(old_history.json()["total_days"], 1)
        self.assertEqual(
            old_history.json()["daily_stats"][0]["metrics"]["anonymous_dau"],
            7,
        )
        self.assertEqual(
            summary.json()["metrics"]["anonymous_active_installation_days"],
            8,
        )
        with closing(self.db_connection()) as conn:
            old_raw_count = conn.execute(
                "SELECT COUNT(1) FROM dau_daily_signals WHERE day_utc = ?",
                (old_day,),
            ).fetchone()[0]
        self.assertEqual(old_raw_count, 0)


if __name__ == "__main__":
    unittest.main()
