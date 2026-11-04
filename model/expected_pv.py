"""Produksi panel yang SEHARUSNYA, dari cuaca, memakai pvlib (model fisik)."""
import pandas as pd
import pvlib


def weather_to_poa(weather: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """weather: index waktu lokal per jam; kolom ghi, dni, dhi (W/m2), temp_air (C),
    wind_speed (m/s, opsional). Return: poa_wm2, temp_cell_c."""
    site, panel = cfg["site"], cfg["panel"]
    idx = weather.index
    if idx.tz is None:
        idx = idx.tz_localize(site["tz"])
    # Open-Meteo memberi rata-rata jam SEBELUMNYA -> posisi matahari di tengah interval
    solpos = pvlib.solarposition.get_solarposition(
        idx - pd.Timedelta(minutes=30), site["latitude"], site["longitude"],
        altitude=site.get("altitude", 0))
    solpos.index = weather.index
    poa = pvlib.irradiance.get_total_irradiance(
        panel["tilt"], panel["azimuth"],
        solpos["apparent_zenith"], solpos["azimuth"],
        weather["dni"], weather["ghi"], weather["dhi"], model="isotropic")
    poa_global = poa["poa_global"].fillna(0).clip(lower=0)
    wind = weather["wind_speed"] if "wind_speed" in weather else 1.0
    temp_cell = pvlib.temperature.faiman(poa_global, weather["temp_air"], wind)
    return pd.DataFrame({"poa_wm2": poa_global, "temp_cell_c": temp_cell})


def expected_from_poa(poa_wm2, temp_cell_c, cfg: dict):
    """Daya DC (W) yang seharusnya, model PVWatts dikurangi rugi sistem."""
    p = cfg["panel"]
    dc = pvlib.pvsystem.pvwatts_dc(poa_wm2, temp_cell_c, p["pdc0_w"], p["gamma_pdc"])
    return (dc * (1 - p["system_loss"])).clip(lower=0)
