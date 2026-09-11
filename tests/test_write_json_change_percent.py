import json

import write_json


def test_build_dashboard_data_includes_change_percent(tmp_path, monkeypatch):
    snapshot = [
        {"code": "1101", "name": "台泥", "date": "2026-09-01", "close": 25.3, "change": 0.9},
    ]
    snapshot_path = tmp_path / "market_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    monkeypatch.setattr(write_json, "SNAPSHOT_PATH", snapshot_path)
    monkeypatch.setattr(write_json.history_store, "load_history", lambda code: [])

    data = write_json.build_dashboard_data()

    stock = data["stocks"][0]
    assert stock["change_percent"] == round(0.9 / 24.4 * 100, 2)
