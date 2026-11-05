"""Latih dan kalibrasi. Jalankan: python -m ml.train"""
import json

import numpy as np
import pandas as pd

from . import detector, residual
from .config import ARTIFACT_DIR, PROCESSED_DIR, load_config
from .features import assemble, peer_expected, sensor_expected


def load_unit(unit, cfg):
    read = lambda name: pd.read_csv(PROCESSED_DIR / name, index_col="timestamp", parse_dates=True)
    hourly = read(f"lareunion_{unit}_hourly.csv")
    hourly["p_actual"] = hourly["p_w"] / cfg["units"][unit]["capacity_w"]
    return assemble(hourly, read("lareunion_weather_hourly.csv"), cfg["site"], cfg["panel"])


def load_sensor():
    return pd.read_csv(PROCESSED_DIR / "lareunion_sensor_hourly.csv", index_col="timestamp", parse_dates=True)


def split(frame, cfg):
    """Periode uji dipisahkan utuh, jadi model tidak pernah melihat cuaca periode uji."""
    tz = cfg["site"]["tz"]
    start, end = (pd.Timestamp(cfg["split"][k], tz=tz) for k in ("test_start", "test_end"))
    in_test = (frame.index >= start) & (frame.index < end)
    return frame[~in_test], frame[in_test]


def calibrate(frame, expected, cfg):
    """Profil derau + batas CUSUM dari data normal yang tidak dipakai melatih barisnya."""
    d = cfg["detector"]
    expected = pd.Series(expected, index=frame.index)
    e = detector.deficit(frame["p_actual"], expected, detector.assessable(frame, expected, d))
    profile = detector.noise_profile(e, frame["clear_index"], d["clear_index_bins"])
    z = detector.standardize(e, frame["clear_index"], profile, d["clear_index_bins"], d["z_clip"])
    h = detector.calibrate_h(z, d["cusum_k"], d["target_false_alarm_per_week"])
    return {"profile": profile, "h": h, "tau_p99": float(e.quantile(0.99))}


def main():
    cfg = load_config()
    train, _ = split(load_unit("inv2", cfg), cfg)
    peer, _ = split(load_unit("inv1", cfg), cfg)
    day = train[train["sun_elevation"] >= cfg["detector"]["min_sun_elevation"]]

    mae, best = residual.tune(day, cfg["model"]["params"], cfg["model"]["grid"], cfg["split"]["n_folds"])
    model = residual.fit(day, best)
    oof = residual.out_of_fold(day, best, cfg["split"]["n_folds"])

    ARTIFACT_DIR.mkdir(exist_ok=True)
    model.save_model(ARTIFACT_DIR / "residual_xgb.ubj")
    calibration = {
        "weather_xgb": calibrate(day, oof, cfg),
        "weather_pvlib": calibrate(day, day["p_pvlib"].to_numpy(), cfg),
        "peer": calibrate(day, peer_expected(day, peer).to_numpy(), cfg),
        "sensor": calibrate(day, sensor_expected(day, load_sensor(), cfg["panel"]).to_numpy(), cfg),
        "threshold_fair_frac": detector.calibrate_threshold(
            day, cfg["site"]["tz"], cfg["detector"]["threshold_hours"],
            cfg["detector"]["target_false_alarm_per_week"]),
        "params": best,
        "mae_oof_xgb": mae,
        "mae_oof_pvlib": float(np.abs(day["p_actual"] - day["p_pvlib"]).mean()),
        "n_train_hours": len(day),
    }
    (ARTIFACT_DIR / "calibration.json").write_text(json.dumps(calibration, indent=2))
    print(json.dumps(calibration, indent=2))


if __name__ == "__main__":
    main()
