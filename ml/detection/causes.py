"""Tebakan penyebab berbasis aturan. Tiap aturan memakai data sampai jam itu saja (bisa jalan langsung)."""
import pandas as pd


def _is_cable_cut(assessed, cfg):
    """Jam terakhir ~0 dibanding seharusnya. Awan tebal pun masih menyisakan arus."""
    last = assessed.iloc[-1]
    return last["p_actual"] / last["p_expected"] < cfg["near_zero_ratio"]


def _is_shading(assessed, cfg, tz):
    """Kekurangan muncul di jam yang sama pada beberapa hari, sementara jam lain normal."""
    local_hour = pd.Series(assessed.index.tz_convert(tz).hour, index=assessed.index)
    by_hour = assessed["deficit"].groupby(local_hour).median()
    if len(by_hour) < 3:
        return False
    worst = by_hour.idxmax()
    other = assessed.loc[local_hour != worst, "deficit"].median()
    deep = assessed.loc[local_hour == worst, "deficit"] > other + cfg["shading_hour_gap"]
    return deep.sum() >= cfg["shading_min_days"] and deep.mean() >= cfg["shading_repeat"]


def _clear_hours(assessed, cfg):
    """Jam cerah, tempat cuaca bisa dipercaya. Kalau terlalu sedikit, pakai semua jam."""
    clear = assessed[assessed["clear_index"] >= cfg["clear_sky_min"]]
    return (clear if len(clear) >= cfg["loose_min_hours"] else assessed).tail(cfg["recent_hours"])


def guess(history, cfg, tz):
    """history = jam-jam sampai saat alarm, berkolom deficit, p_actual, p_expected, clear_index."""
    assessed = history.dropna(subset=["deficit"])
    if assessed.empty:
        return "tidak_diketahui"
    if _is_cable_cut(assessed, cfg):
        return "kabel_putus"
    if _is_shading(assessed, cfg, tz):
        return "bayangan"
    clear = _clear_hours(assessed, cfg)["deficit"]
    if clear.median() >= cfg["soiling_min_deficit"]:
        return "panel_kotor"
    if clear.quantile(0.9) >= cfg["loose_p90_min"]:
        return "konektor_kendor"
    return "tidak_diketahui"


def guess_series(frame, alarm, cfg, tz):
    """Isi penyebab untuk tiap jam alarm, dengan riwayat beberapa hari ke belakang."""
    out = pd.Series("", index=frame.index, dtype=object)
    span = pd.Timedelta(days=cfg["history_days"])
    for t in frame.index[alarm.to_numpy()]:
        out[t] = guess(frame.loc[t - span:t], cfg, tz)
    return out
