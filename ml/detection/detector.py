"""Detektor: simpangan produksi dinilai relatif terhadap ketidakpastian cuaca saat itu.

Cuaca satelit per jam bisa meleset jauh, jadi satu jam menyimpang bukan bukti. Bukti dikumpulkan dengan
CUSUM (Page, 1954): skor naik saat produksi di bawah seharusnya, turun saat normal. Gangguan besar
memicu alarm dalam hitungan jam, gangguan kecil yang menetap tetap terkumpul dalam beberapa hari.
"""
import numpy as np
import pandas as pd


def assessable(frame, expected, cfg):
    return (frame["sun_elevation"] >= cfg["min_sun_elevation"]) & (expected >= cfg["min_expected"])


def deficit(actual, expected, mask):
    """Kekurangan relatif: 0 = sesuai seharusnya, 1 = nol. Jam yang tak bisa dinilai = NaN."""
    return ((expected - actual) / expected).where(mask)


def _sky_bin(clear_index, edges):
    return pd.Series(np.digitize(clear_index.fillna(0), edges), index=clear_index.index)


def noise_profile(e, clear_index, edges):
    """Median dan sebaran kekurangan normal per kondisi langit, dari data out-of-fold."""
    profile = {}
    for sky, group in e.dropna().groupby(_sky_bin(clear_index, edges)):
        q25, q50, q75 = group.quantile([0.25, 0.5, 0.75])
        profile[str(sky)] = {"median": float(q50), "sigma": float((q75 - q25) / 1.349)}
    return profile


def standardize(e, clear_index, profile, edges, z_clip):
    sky = _sky_bin(clear_index, edges).astype(str)
    median = sky.map({k: v["median"] for k, v in profile.items()})
    sigma = sky.map({k: v["sigma"] for k, v in profile.items()})
    return ((e - median) / sigma).clip(-z_clip, z_clip)


def cusum(z, k, h):
    """Skor akumulasi. Jam yang tak bisa dinilai (malam) tidak mengubah skor.

    Skor dibatasi 1,5 x h supaya alarm padam dalam beberapa hari setelah gangguan diperbaiki.
    """
    score, out = 0.0, np.zeros(len(z))
    for i, value in enumerate(z.to_numpy()):
        if not np.isnan(value):
            score = min(max(0.0, score + value - k), 1.5 * h)
        out[i] = score
    return pd.Series(out, index=z.index)


def hysteresis(score, h):
    """Alarm menyala saat skor melewati h dan padam saat skor kembali 0."""
    state, out = False, np.zeros(len(score), dtype=bool)
    for i, value in enumerate(score.to_numpy()):
        state = value > h or (state and value > 0)
        out[i] = state
    return pd.Series(out, index=score.index)


def n_episodes(alarm):
    a = alarm.astype(int).to_numpy()
    return int(((a[1:] == 1) & (a[:-1] == 0)).sum() + a[:1].sum())


def weeks_covered(index):
    return max(len(pd.Index(index.strftime("%Y-%m-%d")).unique()) / 7, 1e-9)


def false_alarm_rate(alarm):
    return n_episodes(alarm) / weeks_covered(alarm.index)


def calibrate_h(z, k, target_per_week):
    """Batas terkecil yang alarm palsunya memenuhi target pada data normal."""
    for h in np.arange(1.0, 60.0, 0.5):
        if false_alarm_rate(hysteresis(cusum(z, k, h), h)) <= target_per_week:
            return float(h)
    raise ValueError("target alarm palsu tidak tercapai sampai h=60; cek data kalibrasi")


def dead_output(frame, expected, cfg):
    """Daya ~0 saat seharusnya jelas menghasilkan: awan setebal apa pun tidak membuat nol."""
    return (frame["p_actual"] < cfg["dead_output"]) & (expected >= cfg["dead_expected"]) & (
        frame["sun_elevation"] >= cfg["min_sun_elevation"])


def consecutive(flag, n):
    """Benar bila flag benar pada n jam yang bisa dinilai berturut-turut."""
    return flag.astype(float).rolling(n, min_periods=n).sum().ge(n)


def threshold_alarm(frame, tz, frac, hours, persist_h=2):
    """Alarm biasa: daya di bawah batas tetap pada jam siang, tanpa melihat cuaca."""
    local_hour = frame.index.tz_convert(tz).hour
    in_window = (local_hour >= hours[0]) & (local_hour < hours[1])
    window = frame.loc[in_window, "p_actual"]
    return consecutive(window < frac, persist_h).reindex(frame.index, fill_value=False)


def calibrate_threshold(frame, tz, hours, target_per_week):
    """Batas tetap terbesar yang alarm palsunya sama dengan target: perbandingan adil dengan usulan."""
    for frac in np.arange(0.60, 0.0, -0.01):
        if false_alarm_rate(threshold_alarm(frame, tz, frac, hours)) <= target_per_week:
            return round(float(frac), 2)
    return 0.0


def battery_full(frame, full_v):
    """Aki penuh: controller mengerem panel, jadi produksi rendah bukan gangguan."""
    return frame["batt_v"] >= full_v if "batt_v" in frame else pd.Series(False, index=frame.index)
