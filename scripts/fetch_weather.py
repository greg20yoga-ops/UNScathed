"""Unduh cuaca historis per jam dari Open-Meteo (gratis, tanpa API key) -> data/raw/weather_openmeteo.csv
Jalankan di laptop lo (butuh internet):  python scripts/fetch_weather.py
Catat sumber & rentang di docs/sumber_data.md."""
import sys
from pathlib import Path
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.config import load_config, ROOT

cfg = load_config()
s = cfg["site"]
params = {
    "latitude": s["latitude"], "longitude": s["longitude"],
    "start_date": cfg["weather"]["start"], "end_date": cfg["weather"]["end"],
    "hourly": "shortwave_radiation,direct_normal_irradiance,diffuse_radiation,temperature_2m,wind_speed_10m,cloud_cover",
    "timezone": s["tz"], "wind_speed_unit": "ms",
}
r = requests.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=60)
r.raise_for_status()
h = r.json()["hourly"]
df = pd.DataFrame(h).rename(columns={
    "time": "timestamp", "shortwave_radiation": "ghi", "direct_normal_irradiance": "dni",
    "diffuse_radiation": "dhi", "temperature_2m": "temp_air", "wind_speed_10m": "wind_speed"})
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.set_index("timestamp").interpolate(limit=3).fillna(0)
out = ROOT / "data" / "raw" / "weather_openmeteo.csv"
df.to_csv(out)
print(f"OK {len(df)} baris -> {out}\nCatat di docs/sumber_data.md: Open-Meteo Historical Weather API, {cfg['weather']['start']}..{cfg['weather']['end']}")
