"""Aturan baterai melemah: tegangan turun terlalu cepat per Ah saat membuang."""
import pandas as pd

DISCHARGE_MIN_A = 0.15
MIN_DAILY_AH = 3
UTC_OFFSET_H = 3  # Afrika Sub-Sahara; zona pasti tidak dicatat dataset


def sag_per_ah(hourly):
    """Penurunan tegangan per Ah saat membuang, per siklus harian. Baterai lemah turun lebih cepat."""
    discharging = hourly[hourly["batt_i_a"] < -DISCHARGE_MIN_A]
    # siklus malam melewati tengah malam, jadi hari dihitung mulai tengah hari
    day = (discharging.index + pd.Timedelta(hours=UTC_OFFSET_H - 12)).normalize()
    grouped = discharging.groupby(day)
    ah = -grouped["batt_i_a"].sum()
    sag = (grouped["batt_v"].first() - grouped["batt_v"].last()) / ah
    return sag[ah >= MIN_DAILY_AH]


def weak_flags(hourly, recent_days, limit):
    """Benar saat sag beberapa hari terakhir melewati batas. Riwayat kurang = belum bisa dinilai."""
    sag = sag_per_ah(hourly.dropna(subset=["batt_v", "batt_i_a"]))
    flagged = sag.rolling(recent_days, min_periods=recent_days).median() > limit
    return flagged.reindex(hourly.index, method="ffill").fillna(False).astype(bool)
