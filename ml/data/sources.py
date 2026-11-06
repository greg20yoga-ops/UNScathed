"""Ringkas data La Réunion (Graillet dkk. 2023, Zenodo, CC BY 4.0) menjadi tabel per jam.

File mentah ±2,6 GB dibaca sebagai aliran per potongan, jadi tidak perlu disimpan di disk.
"""
import pandas as pd

BASE = "https://zenodo.org/api/records/7828879/files/{}/content"
ELECTRICAL = {"inv1": "dt2_electrical_production_inverter_1_with_faults.csv",
              "inv2": "dt3_electrical_production_inverter_2.csv"}
SENSOR = "dt1_solar_and_meteorological_measurement.csv"
CHUNK_ROWS = 2_000_000
SAMPLES_PER_H = {"electrical": 3600 / 7, "sensor": 3600}
MIN_COVERAGE = 0.8


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


def hourly_electrical(unit):
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


def hourly_sensor():
    """Pyranometer + termokopel per jam. Hanya dipakai sebagai pembanding batas atas."""
    def prepare(c):
        return c[["GTI", "TA", "TPV"]]

    s = _sum_by_hour(SENSOR, ["time", "GTI", "TA", "TPV"], prepare)
    n = s[("GTI", "count")]
    out = pd.DataFrame({c.lower(): s[(c, "sum")] / s[(c, "count")] for c in ["GTI", "TA", "TPV"]})
    return out[n >= SAMPLES_PER_H["sensor"] * MIN_COVERAGE].round(2)
