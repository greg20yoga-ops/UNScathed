"""Baterai: data nyata BBOXX (Aitio & Howey 2021, CC BY-NC 4.0; aki 12 V 20 Ah + panel 50 Wp)."""
import numpy as np
import pandas as pd

DISCHARGE_MIN_A = 0.15
MIN_DAILY_AH = 3
UTC_OFFSET_H = 3  # Afrika Sub-Sahara; zona pasti tidak dicatat dataset


def load_npz(path):
    """Berkas BBOXX: unix time, arus (negatif = mengisi), tegangan, suhu.

    Tanda arus dibalik mengikuti kontrak repo: positif = mengisi.
    """
    data = np.load(path, allow_pickle=False)["arr_0"]
    frame = pd.DataFrame({"batt_i_a": -data[:, 1], "batt_v": data[:, 2]},
                         index=pd.to_datetime(data[:, 0], unit="s", utc=True).rename("timestamp"))
    return frame.resample("1h", label="right", closed="right").mean().dropna()


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
