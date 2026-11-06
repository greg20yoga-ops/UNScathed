"""Suntik gangguan buatan ke data normal untuk pengujian. Hanya dipakai pada salinan data uji.

Parameter default menunggu docs/pola_gangguan.md (Bobi).
"""
import numpy as np
import pandas as pd


def _active(frame, start, days):
    return (frame.index >= start) & (frame.index < start + pd.Timedelta(days=days))


def cable_cut(frame, start, cfg, rng, days):
    out = frame.copy()
    hit = _active(frame, start, days)
    out.loc[hit, ["p_actual", "pv_i"]] = 0.0
    return out, hit


def soiling(frame, start, cfg, rng, rate_per_day, days):
    """Kotor bertambah harian, dicuci hujan deras."""
    out = frame.copy()
    hit = _active(frame, start, days)
    tz = cfg["site"]["tz"]
    day = frame.index.tz_convert(tz).normalize()
    rain = frame.groupby(day)["precip"].sum()
    loss_by_day, loss = {}, 0.0
    for d in rain.index[rain.index >= start.tz_convert(tz).normalize()]:
        loss = 0.0 if rain[d] > cfg["faults"]["rain_wash_mm"] else min(
            loss + rate_per_day, cfg["faults"]["soiling_max_loss"])
        loss_by_day[d] = loss
    factor = 1 - pd.Series(day, index=frame.index).map(loss_by_day).fillna(0.0)
    out.loc[hit, "p_actual"] = frame.loc[hit, "p_actual"] * factor[hit]
    return out, hit


def partial_shading(frame, start, cfg, rng, depth, hour, length_h, days):
    out = frame.copy()
    local = frame.index.tz_convert(cfg["site"]["tz"]).hour
    hit = _active(frame, start, days) & (local >= hour) & (local < hour + length_h)
    out.loc[hit, "p_actual"] = frame.loc[hit, "p_actual"] * (1 - depth)
    return out, hit


def loose_connector(frame, start, cfg, rng, days, prob):
    out = frame.copy()
    hit = _active(frame, start, days)
    drop = rng.random(hit.sum()) < prob
    out.loc[hit, "p_actual"] = frame.loc[hit, "p_actual"] * np.where(drop, rng.uniform(0.3, 1.0, hit.sum()), 1.0)
    return out, hit


PATTERNS = {"cable_cut": cable_cut, "soiling": soiling, "partial_shading": partial_shading,
            "loose_connector": loose_connector}


def event_starts(frame, days, cfg, rng, n):
    """Waktu mulai acak pada hari yang datanya ada, kejadian selesai sebelum periode uji habis."""
    tz = cfg["site"]["tz"]
    start_hour = pd.Timedelta(hours=cfg["faults"]["start_hour_local"])
    candidates = frame.index.tz_convert(tz).normalize().unique()
    candidates = candidates[candidates + pd.Timedelta(days=days) <= frame.index[-1]]
    return [t + start_hour for t in rng.choice(candidates, n, replace=len(candidates) < n)]
