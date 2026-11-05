import numpy as np
import pandas as pd
import pytest

from ml import causes, faults, rupiah
from ml.config import load_config

CFG = load_config()
TZ = CFG["site"]["tz"]


def daylight(days=10):
    idx = pd.date_range("2022-03-01", periods=days * 24, freq="h", tz=TZ)
    idx = idx[(idx.hour >= 8) & (idx.hour < 16)]
    return pd.DataFrame({"p_actual": 0.6, "pv_i": 5.0, "pv_v": 30.0, "precip": 0.0}, index=idx)


def history(deficits):
    idx = pd.date_range("2022-03-01 08:00", periods=len(deficits), freq="h", tz=TZ)
    d = pd.Series(deficits, index=idx, dtype=float)
    return pd.DataFrame({"deficit": d, "p_expected": 0.6, "p_actual": 0.6 * (1 - d), "clear_index": 0.8})


def test_cable_cut_zeroes_current_but_keeps_voltage():
    frame = daylight()
    start = pd.Timestamp("2022-03-03 09:00", tz=TZ)
    out, hit = faults.cable_cut(frame, start, CFG, np.random.default_rng(0), days=1)
    assert out.loc[hit, "p_actual"].eq(0).all() and out.loc[hit, "pv_v"].eq(30).all()
    assert out.loc[~hit, "p_actual"].eq(0.6).all()


def test_soiling_grows_then_rain_washes_it():
    frame = daylight()
    frame.loc[frame.index.day == 6, "precip"] = 2.0
    start = pd.Timestamp("2022-03-03 09:00", tz=TZ)
    out, _ = faults.soiling(frame, start, CFG, np.random.default_rng(0), rate_per_day=0.05, days=6)
    by_day = out["p_actual"].groupby(out.index.day).min().round(3)
    assert by_day[5] < by_day[4] < by_day[3] < 0.6
    assert by_day[6] == 0.6


def test_injection_leaves_input_untouched():
    frame = daylight()
    before = frame.copy()
    faults.loose_connector(frame, frame.index[0], CFG, np.random.default_rng(0), days=2, prob=0.3)
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("deficits,expected", [
    ([0.0] * 7 + [1.0], "kabel_putus"),
    ([0.25] * 16, "panel_kotor"),
    ([0.0, 0.0, 0.0, 0.7] * 6, "konektor_kendor"),
])
def test_cause_rules(deficits, expected):
    assert causes.guess(history(deficits), CFG["causes"], TZ) == expected


def test_shading_needs_same_hour_on_several_days():
    idx = daylight(5).index
    d = pd.Series(np.where(idx.hour == 13, 0.6, 0.0), index=idx)
    frame = pd.DataFrame({"deficit": d, "p_expected": 0.6, "p_actual": 0.6 * (1 - d), "clear_index": 0.8})
    assert causes.guess(frame, CFG["causes"], TZ) == "bayangan"


def test_loss_is_zero_without_alarm_and_counts_run_up_hours():
    idx = pd.date_range("2022-03-01 08:00", periods=4, freq="h", tz="UTC")
    actual, expected = pd.Series(0.0, index=idx), pd.Series(50.0, index=idx)
    score = pd.Series([0.0, 3.0, 9.0, 0.0], index=idx)
    alarm = pd.Series([False, False, True, False], index=idx)
    cfg = {"tarif_rp_per_kwh": 1000.0, "biaya_patroli_rp": 500.0, "biaya_baterai_rp": 0.0}
    cause = pd.Series(["", "", "kabel_putus", ""], index=idx)
    assert rupiah.hourly_loss(actual, expected, score, alarm, cause, cfg).tolist() == [0.0, 50.0, 550.0, 0.0]
