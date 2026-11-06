"""Satu jalur skor untuk data historis maupun data alat IoT.

score_unit() tanpa status: cukup kirim riwayat beberapa hari terakhir setiap jam, lalu pakai baris
terakhirnya. Kalau server mati, tidak ada status yang hilang.
"""
import numpy as np
import pandas as pd

from .. import model
from ..schema import CONTRACT_COLUMNS
from . import battery, causes, detector, rupiah


def detect(frame, expected, calibration, cfg):
    """Tambahkan p_expected, deficit, score, alarm ke tabel per jam."""
    d = cfg["detector"]
    out = frame.copy()
    out["p_expected"] = np.asarray(expected, dtype=float)
    full = detector.battery_full(out, cfg["battery"]["full_v"])
    mask = detector.assessable(out, out["p_expected"], d) & ~full
    out["deficit"] = detector.deficit(out["p_actual"], out["p_expected"], mask)
    z = detector.standardize(out["deficit"], out["clear_index"], calibration["profile"],
                             d["clear_index_bins"], d["z_clip"])
    out["score"] = detector.cusum(z, d["cusum_k"], calibration["h"])
    out["alarm"] = detector.hysteresis(out["score"], calibration["h"]) | (
        detector.dead_output(out, out["p_expected"], d) & ~full)
    return out


def battery_alarms(frame, cfg, history=None):
    """Kolom batt_v tidak ada = baterai tidak dipantau."""
    if "batt_v" not in frame:
        off = pd.Series(False, index=frame.index)
        return off, off
    b = cfg["battery"]
    # satu jam kosong bisa cuma paket hilang; dua jam berturut-turut baru dianggap dicabut
    removed = detector.consecutive(frame["batt_v"].isna(), b["missing_hours"])
    source = frame if history is None else history
    weak = battery.weak_flags(source, b["recent_days"], b["weak_sag_v_per_ah"])
    return removed, weak.reindex(frame.index, method="ffill").fillna(False).astype(bool)


def score_unit(frame, artifact, cfg, unit_id, data_source, fault_label=None, battery_history=None):
    """frame dari features.assemble untuk satu unit -> baris kontrak data v1.

    battery_history: rekaman baterai termasuk malam, bila frame hanya berisi jam siang.
    """
    tz, panel_w = cfg["site"]["tz"], cfg["rupiah"]["panel_w"]
    out = detect(frame, model.expected(frame, artifact.model), artifact.calibration, cfg)
    cause = causes.guess_series(out, out["alarm"], cfg["causes"], tz)

    missing, weak = battery_alarms(out, cfg, battery_history)
    cause[weak & ~out["alarm"]] = "baterai_melemah"
    cause[missing] = "baterai_dicabut"
    out["alarm"] = out["alarm"] | missing | weak

    actual_w, expected_w = out["p_actual"] * panel_w, out["p_expected"] * panel_w
    d = cfg["detector"]
    fault = pd.Series("none", index=out.index) if fault_label is None else fault_label
    return pd.DataFrame({
        "timestamp": out.index.tz_convert(tz).strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(r"(\d\d)$", r":\1", regex=True),
        "unit_id": unit_id,
        "pv_actual_w": actual_w.round(2).to_numpy(),
        "pv_expected_w": expected_w.round(2).to_numpy(),
        "batt_v": out["batt_v"].round(2).to_numpy() if "batt_v" in out else np.nan,
        "alarm": out["alarm"].astype(int).to_numpy(),
        "cause_guess": cause.to_numpy(),
        "loss_rp": rupiah.hourly_loss(actual_w, expected_w, out["score"], out["alarm"], cause, cfg["rupiah"]).round(2).to_numpy(),
        "data_label": np.where(fault.to_numpy() == "none", "nyata", "suntikan"),
        "batt_i_a": out["batt_i_a"].round(2).to_numpy() if "batt_i_a" in out else np.nan,
        "alarm_threshold": detector.threshold_alarm(out, tz, d["threshold_frac"], d["threshold_hours"]).astype(int).to_numpy(),
        "data_source": data_source,
        "fault_label": fault.to_numpy(),
    })[CONTRACT_COLUMNS]
