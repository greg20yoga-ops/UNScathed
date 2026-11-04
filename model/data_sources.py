"""Tiga sumber data -> satu format kanonik (DataFrame, index waktu lokal tanpa tz):
   poa_wm2, temp_cell_c, cloud_idx (0 cerah .. 1 mendung), expected_w, pv_actual_w
   + atribut df.attrs["source"] sebagai LABEL (sintetis / nyata)."""
import numpy as np
import pandas as pd
import pvlib

from .config import ROOT
from .expected_pv import weather_to_poa, expected_from_poa


def simulate_actual(poa, temp_cell, expected, seed=0):
    """Produksi 'aktual' SINTETIS: model + bias + efisiensi turun saat redup + noise.
    HANYA untuk demo/uji pipeline. Beri label SINTETIS di proposal."""
    rng = np.random.default_rng(seed)
    eff = 0.95 - 0.12 * np.exp(-poa / 150.0)
    noise = rng.normal(0, 0.02, len(expected))
    return (expected * eff * (1 + noise)).clip(lower=0)


def load_synthetic(cfg, days=120, seed=0, start="2025-03-01"):
    """Cuaca + produksi sintetis penuh (tanpa internet)."""
    site = cfg["site"]
    times = pd.date_range(start, periods=days * 24, freq="h", tz=site["tz"])
    loc = pvlib.location.Location(site["latitude"], site["longitude"], site["tz"], site.get("altitude", 0))
    clear = loc.get_clearsky(times, model="simplified_solis")
    zen = loc.get_solarposition(times)["apparent_zenith"]
    rng = np.random.default_rng(seed)
    day_kt = rng.choice([0.85, 0.55, 0.25], size=days, p=[0.4, 0.35, 0.25])
    ar = np.zeros(len(times))
    for i in range(1, len(ar)):
        ar[i] = 0.8 * ar[i - 1] + rng.normal(0, 0.06)
    kt = np.clip(np.repeat(day_kt, 24) + ar, 0.05, 1.0)
    ghi = clear["ghi"] * kt
    dec = pvlib.irradiance.erbs(ghi, zen, times)
    hour = times.hour.values
    weather = pd.DataFrame({
        "ghi": ghi, "dni": dec["dni"].fillna(0), "dhi": dec["dhi"].fillna(0),
        "temp_air": 27 + 4 * np.sin((hour - 9) / 24 * 2 * np.pi) - 2 * (1 - kt),
        "wind_speed": rng.uniform(0.5, 4, len(times))}, index=times)
    return _finish(weather, 1 - kt, cfg, seed, "SINTETIS (cuaca + produksi buatan)")


def load_openmeteo(cfg, seed=0):
    """Cuaca NYATA (Open-Meteo, hasil scripts/fetch_weather.py) + produksi aktual SINTETIS."""
    f = ROOT / "data" / "raw" / "weather_openmeteo.csv"
    if not f.exists():
        raise FileNotFoundError("Jalankan dulu: python scripts/fetch_weather.py")
    w = pd.read_csv(f, index_col=0, parse_dates=True)
    cc = w["cloud_cover"] / 100.0 if "cloud_cover" in w else pd.Series(0.5, index=w.index)
    return _finish(w, cc, cfg, seed, "cuaca NYATA Open-Meteo + produksi aktual SINTETIS")


def _finish(weather, cloud_idx, cfg, seed, label):
    p = weather_to_poa(weather, cfg)
    exp = expected_from_poa(p["poa_wm2"], p["temp_cell_c"], cfg)
    df = pd.DataFrame({
        "poa_wm2": p["poa_wm2"], "temp_cell_c": p["temp_cell_c"],
        "cloud_idx": np.asarray(cloud_idx), "expected_w": exp,
        "pv_actual_w": simulate_actual(p["poa_wm2"], p["temp_cell_c"], exp, seed)})
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    df.attrs["source"] = label
    return df


def load_kaggle(cfg, folder=None, plant=1):
    """Kaggle 'Solar Power Generation Data' (Plant_1 / Plant_2).
    Taruh 4 file CSV aslinya di data/raw/kaggle/. Produksi aktual NYATA + irradiasi NYATA.
    Skala daya dinormalkan ke kelas panel 50 Wp memakai kuantil 99 (TANPA label gangguan)."""
    folder = folder or ROOT / "data" / "raw" / "kaggle"
    gen = pd.read_csv(f"{folder}/Plant_{plant}_Generation_Data.csv")
    wea = pd.read_csv(f"{folder}/Plant_{plant}_Weather_Sensor_Data.csv")
    gen["DATE_TIME"] = pd.to_datetime(gen["DATE_TIME"], dayfirst=True, errors="coerce")
    wea["DATE_TIME"] = pd.to_datetime(wea["DATE_TIME"], errors="coerce")
    g = gen.dropna(subset=["DATE_TIME"]).groupby("DATE_TIME")["DC_POWER"].mean()
    w = wea.dropna(subset=["DATE_TIME"]).set_index("DATE_TIME")[["IRRADIATION", "AMBIENT_TEMPERATURE", "MODULE_TEMPERATURE"]]
    df = pd.concat([g.rename("dc"), w], axis=1, join="inner").sort_index()
    poa = df["IRRADIATION"] * 1000.0          # kW/m2 -> W/m2
    tcell = df["MODULE_TEMPERATURE"]
    exp = expected_from_poa(poa, tcell, cfg)
    scale = exp.quantile(0.99) / df["dc"].quantile(0.99)
    out = pd.DataFrame({
        "poa_wm2": poa, "temp_cell_c": tcell,
        "cloud_idx": (1 - poa / poa.rolling("5D", min_periods=1).quantile(0.95).clip(lower=50)).clip(0, 1),
        "expected_w": exp, "pv_actual_w": df["dc"] * scale})
    out.attrs["source"] = f"NYATA Kaggle Solar Power Generation Plant_{plant} (skala dinormalkan ke 50 Wp)"
    return out.dropna()
