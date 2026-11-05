"""Pintu masuk data alat IoT: pembacaan mentah -> tabel per jam. Kontrak: docs/kontrak_telemetri.md"""
import pandas as pd

REQUIRED = ["timestamp", "unit_id", "pv_v", "pv_i"]
OPTIONAL = ["batt_v", "batt_i_a"]
LIMITS = {"pv_v": (0, 100), "pv_i": (0, 30), "batt_v": (0, 20), "batt_i_a": (-40, 40)}
MIN_SAMPLES_PER_H = 3


def validate(readings):
    """Buang baris rusak dari perangkat. Kolom hilang = salah kontrak, jadi langsung gagal."""
    missing = [c for c in REQUIRED if c not in readings]
    if missing:
        raise ValueError(f"kolom telemetri hilang: {', '.join(missing)}")
    clean = readings.reindex(columns=REQUIRED + OPTIONAL).copy()
    clean["timestamp"] = pd.to_datetime(clean["timestamp"], utc=True, format="ISO8601", errors="coerce")
    for col, (low, high) in LIMITS.items():
        value = pd.to_numeric(clean[col], errors="coerce")
        clean[col] = value.where(value.between(low, high))
    return clean.dropna(subset=REQUIRED).drop_duplicates(["unit_id", "timestamp"])


def to_hourly(readings, capacity_w):
    """Per unit per jam, indeks = akhir jam (UTC). batt_v kosong = data baterai memang tidak terkirim."""
    clean = validate(readings)
    clean["p_w"] = clean["pv_v"] * clean["pv_i"]
    hour = clean["timestamp"].dt.ceil("h").rename("timestamp")
    agg = {"p_w": "mean", "pv_v": "mean", "pv_i": "mean", "batt_v": "mean", "batt_i_a": "mean"}
    grouped = clean.groupby(["unit_id", hour])
    out = grouped.agg(agg)
    out = out[grouped.size() >= MIN_SAMPLES_PER_H].reset_index("unit_id")
    out["p_actual"] = out.pop("p_w") / capacity_w
    return out
