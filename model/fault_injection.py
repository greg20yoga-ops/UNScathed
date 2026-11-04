"""Suntik gangguan BUATAN ke data normal. Dipakai karena data publik tidak berlabel gangguan.
Pola & parameter dibaca dari config.yaml (isi dari docs/pola_gangguan.md Bobi)."""
import numpy as np
import pandas as pd


def inject(df: pd.DataFrame, pattern: str, start: pd.Timestamp, params: dict, pdc0: float) -> pd.DataFrame:
    d = df.copy()
    d["fault_label"] = "none"
    active = d.index >= start
    d["fault_active"] = active
    act = d["pv_actual_w"].values.copy()
    if pattern == "soiling":
        days = np.clip((d.index - start).total_seconds() / 86400.0, 0, None)
        loss = np.minimum(params["max_loss"], params["rate_per_day"] * days)
        act = act * (1 - loss)
    elif pattern == "cable_cut":
        act = np.where(active, act * params["residual"], act)
    elif pattern == "partial_shading":
        h0, h1 = params["hours"]
        m = active & (d.index.hour >= h0) & (d.index.hour < h1)
        act = np.where(m, act * (1 - params["depth"]), act)
    elif pattern == "derating":
        cap = params["cap_frac"] * pdc0
        act = np.where(active, np.minimum(act, cap), act)
    else:
        raise ValueError(f"pola tidak dikenal: {pattern}")
    d["pv_actual_w"] = act
    d.loc[active, "fault_label"] = pattern
    return d
