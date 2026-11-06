"""Semua sumber data -> satu bentuk: tabel per jam, indeks UTC akhir jam.

Sumber baru cukup menambah satu fungsi pembaca di sini; tahap berikutnya tidak berubah.
"""
import numpy as np
import pandas as pd

# La Réunion (Graillet dkk. 2023, Zenodo, CC BY 4.0): ±2,6 GB dibaca sebagai aliran, tidak disimpan di disk
BASE = "https://zenodo.org/api/records/7828879/files/{}/content"
ELECTRICAL = {"inv1": "dt2_electrical_production_inverter_1_with_faults.csv",
              "inv2": "dt3_electrical_production_inverter_2.csv"}
SENSOR = "dt1_solar_and_meteorological_measurement.csv"
CHUNK_ROWS = 2_000_000
SAMPLES_PER_H = {"electrical": 3600 / 7, "sensor": 3600}
MIN_COVERAGE = 0.8

# Telemetri alat IoT, kontrak: docs/kontrak_telemetri.md
TELEMETRY_REQUIRED = ["timestamp", "unit_id", "pv_v", "pv_i"]
TELEMETRY_OPTIONAL = ["batt_v", "batt_i_a"]
TELEMETRY_LIMITS = {"pv_v": (0, 100), "pv_i": (0, 30), "batt_v": (0, 20), "batt_i_a": (-40, 40)}
MIN_READINGS_PER_H = 3


def _hour_end(time_col):
    ts = pd.to_datetime(time_col, utc=True, format="ISO8601")
    return ts.dt.ceil("h").rename("timestamp")


def _sum_by_hour(file_name, usecols, prepare):
    """Jumlah + cacah per jam lintas potongan, supaya rata-rata per jam tepat."""
    totals = []
    for chunk in pd.read_csv(BASE.format(file_name), usecols=usecols, chunksize=CHUNK_ROWS):
        frame = prepare(chunk)
        hour = _hour_end(chunk["time"])
        totals.append(frame.groupby(hour.values).agg(["sum", "count"]))
    merged = pd.concat(totals).groupby(level=0).sum()
    merged.index = pd.DatetimeIndex(merged.index, tz="UTC", name="timestamp")
    return merged


def lareunion_electrical(unit):
    """Daya DC per jam dalam watt, plus tegangan, arus, dan kode gangguan dominan."""
    has_label = unit == "inv1"
    usecols = ["time", "Ia", "Va"] + (["Fault"] if has_label else [])

    def prepare(c):
        frame = pd.DataFrame({"p_w": c["Ia"] * c["Va"], "pv_v": c["Va"], "pv_i": c["Ia"]})
        if has_label:
            frame["faulty"] = (c["Fault"].fillna(0) > 0).astype(float)
            frame["fault_sum"] = c["Fault"].fillna(0)
        return frame

    s = _sum_by_hour(ELECTRICAL[unit], usecols, prepare)
    n = s[("p_w", "count")]
    out = pd.DataFrame({c: s[(c, "sum")] / n for c in ["p_w", "pv_v", "pv_i"]})
    out["n_samples"] = n
    # shortcut: kode gangguan per jam dari rata-rata baris berlabel; satu jam diasumsikan satu jenis bayangan
    faulty_n = s[("faulty", "sum")] if has_label else 0.0
    out["fault_code"] = (s[("fault_sum", "sum")] / faulty_n).where(faulty_n >= n / 2, 0.0) if has_label else 0.0
    return out[n >= SAMPLES_PER_H["electrical"] * MIN_COVERAGE]


def lareunion_sensor():
    """Pyranometer + termokopel per jam. Hanya dipakai sebagai pembanding batas atas."""
    def prepare(c):
        return c[["GTI", "TA", "TPV"]]

    s = _sum_by_hour(SENSOR, ["time", "GTI", "TA", "TPV"], prepare)
    n = s[("GTI", "count")]
    out = pd.DataFrame({c.lower(): s[(c, "sum")] / s[(c, "count")] for c in ["GTI", "TA", "TPV"]})
    return out[n >= SAMPLES_PER_H["sensor"] * MIN_COVERAGE].round(2)


def bboxx_hourly(path):
    """Berkas BBOXX (Aitio & Howey 2021, CC BY-NC 4.0): unix time, arus (negatif = mengisi), tegangan, suhu.

    Tanda arus dibalik mengikuti kontrak repo: positif = mengisi.
    """
    data = np.load(path, allow_pickle=False)["arr_0"]
    frame = pd.DataFrame({"batt_i_a": -data[:, 1], "batt_v": data[:, 2]},
                         index=pd.to_datetime(data[:, 0], unit="s", utc=True).rename("timestamp"))
    return frame.resample("1h", label="right", closed="right").mean().dropna()


def validate_telemetry(readings):
    """Buang baris rusak dari perangkat. Kolom hilang = salah kontrak, jadi langsung gagal."""
    missing = [c for c in TELEMETRY_REQUIRED if c not in readings]
    if missing:
        raise ValueError(f"kolom telemetri hilang: {', '.join(missing)}")
    clean = readings.reindex(columns=TELEMETRY_REQUIRED + TELEMETRY_OPTIONAL).copy()
    clean["timestamp"] = pd.to_datetime(clean["timestamp"], utc=True, format="ISO8601", errors="coerce")
    for col, (low, high) in TELEMETRY_LIMITS.items():
        value = pd.to_numeric(clean[col], errors="coerce")
        clean[col] = value.where(value.between(low, high))
    return clean.dropna(subset=TELEMETRY_REQUIRED).drop_duplicates(["unit_id", "timestamp"])


def telemetry_hourly(readings, capacity_w):
    """Per unit per jam. batt_v kosong = data baterai memang tidak terkirim."""
    clean = validate_telemetry(readings)
    clean["p_w"] = clean["pv_v"] * clean["pv_i"]
    hour = clean["timestamp"].dt.ceil("h").rename("timestamp")
    agg = {"p_w": "mean", "pv_v": "mean", "pv_i": "mean", "batt_v": "mean", "batt_i_a": "mean"}
    grouped = clean.groupby(["unit_id", hour])
    out = grouped.agg(agg)
    out = out[grouped.size() >= MIN_READINGS_PER_H].reset_index("unit_id")
    out["p_actual"] = out.pop("p_w") / capacity_w
    return out
