"""Produksi seharusnya: koreksi XGBoost di atas pvlib, kalibrasi alarm, dan simpan-muat model per lokasi."""
import json
from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

from .config import ARTIFACT_DIR, DEFAULT_SITE
from .detection import detector
from .schema import FEATURES

MODEL_FILE, CALIBRATION_FILE = "residual_xgb.ubj", "calibration.json"


@dataclass
class Artifact:
    """Model koreksi opsional + hasil kalibrasi. model=None berarti pvlib saja."""
    model: XGBRegressor | None
    calibration: dict


def _regressor(params):
    return XGBRegressor(n_jobs=-1, **params)


def _fit_predict(train, other, params):
    model = _regressor(params).fit(train[FEATURES], train["p_actual"] - train["p_pvlib"])
    return model, expected(other, model)


def expected(frame, model=None):
    """Produksi seharusnya per kapasitas. Tanpa model = pvlib saja (awal pemasangan di lokasi baru)."""
    base = frame["p_pvlib"].to_numpy()
    if model is None:
        return base
    return np.clip(base + model.predict(frame[FEATURES]), 0, None)


def out_of_fold(frame, params, n_folds):
    """Prediksi tiap baris dari model yang tidak melihat hari itu.

    Dibagi per tanggal: dua jam di hari yang sama hampir kembar, jadi KFold acak akan bocor.
    """
    days = frame.index.tz_convert("UTC").strftime("%Y-%m-%d")
    pred = np.empty(len(frame))
    for fit_idx, val_idx in GroupKFold(n_folds).split(frame, groups=days):
        pred[val_idx] = _fit_predict(frame.iloc[fit_idx], frame.iloc[val_idx], params)[1]
    return pred


def tune(frame, base_params, grid, n_folds):
    """Pilih parameter dengan MAE out-of-fold terkecil."""
    keys = list(grid)
    results = []
    for values in product(*grid.values()):
        params = {**base_params, **dict(zip(keys, values))}
        mae = float(np.abs(frame["p_actual"] - out_of_fold(frame, params, n_folds)).mean())
        results.append((mae, params))
    return min(results, key=lambda r: r[0])


def fit(frame, params):
    return _regressor(params).fit(frame[FEATURES], frame["p_actual"] - frame["p_pvlib"])


def calibrate(frame, expected_p, cfg):
    """Profil derau + batas CUSUM dari data normal yang tidak dipakai melatih barisnya."""
    d = cfg["detector"]
    expected_p = pd.Series(expected_p, index=frame.index)
    e = detector.deficit(frame["p_actual"], expected_p, detector.assessable(frame, expected_p, d))
    profile = detector.noise_profile(e, frame["clear_index"], d["clear_index_bins"])
    z = detector.standardize(e, frame["clear_index"], profile, d["clear_index_bins"], d["z_clip"])
    h = detector.calibrate_h(z, d["cusum_k"], d["target_false_alarm_per_week"])
    return {"profile": profile, "h": h, "tau_p99": float(e.quantile(0.99))}


def train_site(frame, cfg, name, references=None):
    """Latih + kalibrasi dari jam-jam normal, lalu simpan ke artifacts/<name>/.

    references: acuan tambahan {nama: produksi per jam} yang ikut dikalibrasi.
    """
    day = frame[frame["sun_elevation"] >= cfg["detector"]["min_sun_elevation"]]
    m, d = cfg["model"], cfg["detector"]
    mae, best = tune(day, m["params"], m["grid"], m["n_folds"])
    oof = out_of_fold(day, best, m["n_folds"])
    calibration = {
        "weather_xgb": calibrate(day, oof, cfg),
        "weather_pvlib": calibrate(day, day["p_pvlib"].to_numpy(), cfg),
        **{key: calibrate(day, value.reindex(day.index).to_numpy(), cfg) for key, value in (references or {}).items()},
        "threshold_fair_frac": detector.calibrate_threshold(
            day, cfg["site"]["tz"], d["threshold_hours"], d["target_false_alarm_per_week"]),
        "params": best,
        "mae_oof_xgb": mae,
        "mae_oof_pvlib": float(np.abs(day["p_actual"] - day["p_pvlib"]).mean()),
        "n_train_hours": len(day),
    }
    folder = ARTIFACT_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    fit(day, best).save_model(folder / MODEL_FILE)
    (folder / CALIBRATION_FILE).write_text(json.dumps(calibration, indent=2))
    return calibration


def load_calibration(name):
    return json.loads((ARTIFACT_DIR / name / CALIBRATION_FILE).read_text())


def load_artifact(name, kind="weather_xgb"):
    """Model lokasi itu. Lokasi yang belum dilatih memakai pvlib + profil derau bawaan."""
    if not (ARTIFACT_DIR / name / MODEL_FILE).exists():
        return Artifact(None, load_calibration(DEFAULT_SITE)["weather_pvlib"])
    if kind == "weather_pvlib":
        return Artifact(None, load_calibration(name)[kind])
    model = XGBRegressor()
    model.load_model(ARTIFACT_DIR / name / MODEL_FILE)
    return Artifact(model, load_calibration(name)[kind])
