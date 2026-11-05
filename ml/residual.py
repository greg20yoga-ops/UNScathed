"""Koreksi XGBoost di atas pvlib: belajar kesalahan khas lokasi dari jam-jam normal."""
from itertools import product

import numpy as np
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

from .schema import FEATURES


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
