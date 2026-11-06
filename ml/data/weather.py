"""Ambil cuaca per jam dari Open-Meteo.

Radiasi dari produk satelit, suhu/angin/awan/hujan dari model cuaca. Indeks hasil = UTC, akhir jam,
sama dengan konvensi radiasi Open-Meteo (nilai jam T = rata-rata jam sebelum T).
"""
import pandas as pd
import requests

SATELLITE_URL = "https://satellite-api.open-meteo.com/v1/archive"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

RADIATION = {"shortwave_radiation": "ghi", "direct_normal_irradiance": "dni", "diffuse_radiation": "dhi"}
METEO = {"temperature_2m": "temp_air", "wind_speed_10m": "wind_speed", "cloud_cover": "cloud_cover",
         "precipitation": "precip"}
# Himawari melewati dua langkah waktu tiap hari untuk perawatan satelit
MAX_GAP_H = 3


def _get(url, site, variables, **params):
    r = requests.get(url, timeout=120, params={
        "latitude": site["latitude"], "longitude": site["longitude"], "timezone": "UTC",
        "wind_speed_unit": "ms", "hourly": ",".join(variables), **params})
    r.raise_for_status()
    h = r.json()["hourly"]
    df = pd.DataFrame(h).rename(columns=variables)
    df.index = pd.to_datetime(df.pop("time"), utc=True)
    df.index.name = "timestamp"
    return df


def fetch_history(site, start, end):
    dates = {"start_date": start, "end_date": end}
    rad = _get(SATELLITE_URL, site, RADIATION, models=site["satellite_model"], **dates)
    meteo = _get(ARCHIVE_URL, site, METEO, **dates)
    return rad.join(meteo).interpolate(limit=MAX_GAP_H, limit_area="inside")


def fetch_recent(site, past_days=8, satellite_model="satellite_radiation_seamless"):
    """Cuaca beberapa hari terakhir untuk skor langsung di lapangan (Himawari untuk Indonesia)."""
    rad = _get(SATELLITE_URL, site, RADIATION, models=satellite_model, past_days=past_days, forecast_days=1)
    meteo = _get(FORECAST_URL, site, METEO, past_days=past_days, forecast_days=1)
    return rad.join(meteo, how="inner").interpolate(limit=MAX_GAP_H, limit_area="inside")
