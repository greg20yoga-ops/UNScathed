import numpy as np
import pandas as pd

from ml.detection import detector


def index(n):
    return pd.date_range("2022-03-01 04:00", periods=n, freq="h", tz="UTC")


def test_deficit_is_nan_when_not_assessable():
    actual = pd.Series([0.5, 0.5])
    expected = pd.Series([1.0, 1.0])
    e = detector.deficit(actual, expected, pd.Series([True, False]))
    assert e[0] == 0.5 and np.isnan(e[1])


def test_cusum_accumulates_ignores_night_and_never_negative():
    z = pd.Series([3.0, np.nan, 3.0, -3.0, -3.0, -3.0], index=index(6))
    assert detector.cusum(z, 0.5, 8.5).tolist() == [2.5, 2.5, 5.0, 1.5, 0.0, 0.0]


def test_cusum_score_is_capped_so_alarm_can_clear():
    z = pd.Series([3.0] * 100, index=index(100))
    assert detector.cusum(z, 0.5, 8.5).max() == 1.5 * 8.5


def test_one_cloudy_hour_alone_never_alarms():
    z = pd.Series([3.0] + [0.0] * 5, index=index(6))
    assert not detector.hysteresis(detector.cusum(z, 0.5, 8.5), 8.5).any()


def test_persistent_small_deviation_eventually_alarms():
    z = pd.Series([1.0] * 30, index=index(30))
    assert detector.hysteresis(detector.cusum(z, 0.5, 8.5), 8.5).iloc[-1]


def test_hysteresis_stays_on_until_score_returns_to_zero():
    score = pd.Series([0, 9, 4, 1, 0, 3], index=index(6), dtype=float)
    assert detector.hysteresis(score, 8.5).tolist() == [False, True, True, True, False, False]


def test_calibrate_h_meets_target():
    rng = np.random.default_rng(0)
    z = pd.Series(rng.normal(0, 1, 2000), index=index(2000)).clip(-3, 3)
    h = detector.calibrate_h(z, 0.5, 0.5)
    assert detector.false_alarm_rate(detector.hysteresis(detector.cusum(z, 0.5, h), h)) <= 0.5


def test_threshold_alarm_ignores_night_and_needs_two_hours():
    idx = pd.date_range("2022-03-01 05:00", periods=4, freq="h", tz="UTC")  # 09-12 lokal
    frame = pd.DataFrame({"p_actual": [0.1, 0.5, 0.1, 0.1]}, index=idx)
    alarm = detector.threshold_alarm(frame, "Indian/Reunion", 0.2, [9, 15])
    assert alarm.tolist() == [False, False, False, True]


def test_battery_full_gate_handles_missing_column():
    frame = pd.DataFrame({"p_actual": [0.1]}, index=index(1))
    assert not detector.battery_full(frame, 14.4).any()
