"""Dua jenis alarm pada data yang SAMA:
 1) threshold_detector  : alarm biasa (daya < ambang tetap)
 2) ratio_detector      : alarm sadar-cuaca (aktual / seharusnya dari cuaca)"""
import numpy as np
import pandas as pd


def _consecutive(b: pd.Series, k: int) -> pd.Series:
    if k <= 1:
        return b.fillna(False).astype(bool)
    s = b.fillna(False).astype(int).rolling(k, min_periods=k).sum()
    return s.eq(k).fillna(False)


def _latch(trigger: np.ndarray, clear: np.ndarray) -> np.ndarray:
    state, out = False, np.zeros(len(trigger), dtype=bool)
    for i, (t, c) in enumerate(zip(trigger, clear)):
        if t:
            state = True
        elif c:
            state = False
        out[i] = state
    return out


def threshold_detector(df, cfg, sph):
    dcfg, pdc0 = cfg["detector"], cfg["panel"]["pdc0_w"]
    h0, h1 = dcfg["threshold_hours"]
    low = (df["pv_actual_w"] < dcfg["threshold_frac"] * pdc0) & (df.index.hour >= h0) & (df.index.hour < h1)
    return _consecutive(low, max(1, int(dcfg["consecutive_h"] * sph)))


def ratio_detector(df, expected_col, cfg, sph):
    dcfg, pdc0 = cfg["detector"], cfg["panel"]["pdc0_w"]
    valid = df[expected_col] > cfg["data"]["min_expected_frac"] * pdc0
    ratio = (df["pv_actual_w"] / df[expected_col]).where(valid)
    w = max(3, int(dcfg["window_h"] * sph))
    med = ratio.rolling(w, min_periods=max(2, w // 2)).quantile(dcfg.get("ratio_quantile", 0.5))
    trigger = _consecutive((med < dcfg["ratio_thr"]).fillna(False), max(1, int(dcfg["consecutive_h"] * sph)))
    # alarm baru padam bila sehat terus-menerus >= 2x durasi pemicu (hindari berkedip tiap hari)
    clear = _consecutive((med > dcfg["ratio_clear"]).fillna(False), max(1, int(2 * dcfg["consecutive_h"] * sph)))
    alarm = pd.Series(_latch(trigger.values, clear.values), index=df.index)
    return alarm, ratio


def episodes(alarm: pd.Series, gap_steps: int):
    """Kumpulkan alarm menjadi kejadian (start, end); jeda < gap_steps dianggap satu kejadian."""
    idx = np.flatnonzero(alarm.values)
    if len(idx) == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > gap_steps:
            out.append((alarm.index[s], alarm.index[p]))
            s = i
        p = i
    out.append((alarm.index[s], alarm.index[p]))
    return out
