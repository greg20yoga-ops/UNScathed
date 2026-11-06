"""Jalur IoT dari pembacaan mentah sampai file yang dibaca dashboard, tanpa internet."""
import numpy as np
import pandas as pd
import pytest

from ml import model, service
from ml.config import load_config
from ml.data.sources import telemetry_hourly, validate_telemetry
from ml.schema import CONTRACT_COLUMNS, CAUSES

CALIBRATION = {"profile": {str(i): {"median": 0.0, "sigma": 0.15} for i in range(3)}, "h": 8.5}


def weather(days=9):
    idx = pd.date_range("2026-10-01", periods=days * 24, freq="h", tz="UTC")
    hour = idx.tz_convert("Asia/Makassar").hour + idx.tz_convert("Asia/Makassar").minute / 60
    ghi = np.clip(np.sin((hour - 6) / 12 * np.pi), 0, None) * 900
    return pd.DataFrame({"ghi": ghi, "dni": ghi * 0.8, "dhi": ghi * 0.2, "temp_air": 28.0, "wind_speed": 2.0,
                         "cloud_cover": 10.0, "precip": 0.0}, index=idx)


def readings(cut_from=None, batt_gone_from=None):
    """Panel 50 Wp 18 V, baca tiap 10 menit."""
    wx = weather()
    idx = pd.date_range(wx.index[0], wx.index[-1], freq="10min")
    ghi = wx["ghi"].reindex(idx, method="nearest").to_numpy()
    current = 50 * ghi / 1000 * 0.75 / 18
    frame = pd.DataFrame({"timestamp": idx.strftime("%Y-%m-%dT%H:%M:%S+00:00"), "unit_id": "PJU-01",
                          "pv_v": 18.0, "pv_i": current, "batt_v": 12.8, "batt_i_a": 1.0})
    if cut_from:
        frame.loc[idx >= pd.Timestamp(cut_from, tz="UTC"), "pv_i"] = 0.0
    if batt_gone_from:
        frame.loc[idx >= pd.Timestamp(batt_gone_from, tz="UTC"), ["batt_v", "batt_i_a"]] = np.nan
    return frame


@pytest.fixture(autouse=True)
def pvlib_only(monkeypatch):
    """Skor memakai kalibrasi tetap, supaya test tidak bergantung pada hasil latih."""
    monkeypatch.setattr(service, "load_artifact", lambda site: model.Artifact(None, CALIBRATION))


def score(frame):
    return service.score(frame, "contoh", weather=weather())


def test_contract_columns_and_values():
    out = score(readings())
    assert list(out.columns) == CONTRACT_COLUMNS
    assert out["timestamp"].str.fullmatch(r".*\+08:00").all()
    assert set(out["cause_guess"]) <= CAUSES | {""}
    assert out["pv_actual_w"].between(0, 60).all()


def test_healthy_unit_stays_quiet():
    assert score(readings())["alarm"].sum() == 0


def test_cable_cut_alarms_within_the_day():
    out = score(readings(cut_from="2026-10-06 01:00"))
    hits = out[out["alarm"] == 1]
    assert hits.iloc[0]["timestamp"].startswith("2026-10-06")
    assert hits.iloc[0]["cause_guess"] == "kabel_putus"
    assert out["loss_rp"].sum() > 0


def test_removed_battery_alarms_immediately():
    out = score(readings(batt_gone_from="2026-10-06 01:00"))
    hits = out[out["alarm"] == 1]
    assert hits.iloc[0]["cause_guess"] == "baterai_dicabut"


def test_full_battery_suppresses_false_alarm():
    frame = readings(cut_from="2026-10-06 01:00")
    frame["batt_v"] = 14.5  # controller mengerem panel saat aki penuh, arus turun tanpa gangguan
    assert score(frame)["alarm"].sum() == 0


def test_validate_rejects_missing_columns():
    with pytest.raises(ValueError, match="pv_i"):
        validate_telemetry(pd.DataFrame({"timestamp": [], "unit_id": [], "pv_v": []}))


def test_validate_drops_bad_rows_and_duplicates():
    frame = pd.DataFrame({"timestamp": ["2026-10-01T10:00:00+08:00", "2026-10-01T10:00:00+08:00", "bukan-waktu",
                                        "2026-10-01T10:10:00+08:00"],
                          "unit_id": "PJU-01", "pv_v": [18, 18, 18, 999], "pv_i": [1, 1, 1, 1]})
    assert len(validate_telemetry(frame)) == 1


def test_to_hourly_uses_hour_end_and_mean_power():
    stamps = [f"2026-10-01T10:{m:02d}:00+00:00" for m in (10, 20, 30)]
    frame = pd.DataFrame({"timestamp": stamps, "unit_id": "PJU-01", "pv_v": 10.0, "pv_i": [1.0, 2.0, 3.0]})
    out = telemetry_hourly(frame, 50)
    assert out.index[0] == pd.Timestamp("2026-10-01 11:00", tz="UTC")
    assert out["p_actual"].iloc[0] == pytest.approx(20 / 50)


def test_score_rejects_empty_telemetry():
    empty = pd.DataFrame({"timestamp": ["rusak"], "unit_id": ["PJU-01"], "pv_v": [18], "pv_i": [1]})
    with pytest.raises(ValueError, match="tidak ada telemetri"):
        score(empty)


@pytest.mark.parametrize("site", ["../rahasia", "tidak-ada"])
def test_site_name_is_validated(site):
    with pytest.raises(ValueError, match="lokasi"):
        load_config(site)


def test_train_saves_site_model_and_score_can_use_it(monkeypatch, tmp_path):
    monkeypatch.setattr(model, "ARTIFACT_DIR", tmp_path)
    service.train(readings(), "contoh", weather=weather())
    assert (tmp_path / "contoh" / model.MODEL_FILE).exists()
    assert model.load_artifact("contoh").model is not None


def test_train_needs_one_reference_unit():
    two_units = pd.concat([readings(), readings().assign(unit_id="PJU-02")])
    with pytest.raises(ValueError, match="satu unit"):
        service.train(two_units, "contoh", weather=weather())
