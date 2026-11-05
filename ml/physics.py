"""Estimasi fisika produksi panel (per kapasitas, 0..1) dari cuaca, memakai pvlib."""
import pandas as pd
import pvlib

HOUR_MID = pd.Timedelta(minutes=30)


def estimate(weather, site, panel):
    """weather berindeks UTC akhir jam dengan kolom ghi, dni, dhi, temp_air, wind_speed."""
    # radiasi = rata-rata jam sebelumnya, jadi posisi matahari diambil di tengah jam itu
    times = weather.index - HOUR_MID
    sun = pvlib.solarposition.get_solarposition(times, site["latitude"], site["longitude"],
                                                altitude=site["altitude"])
    sun.index = weather.index
    dni_extra = pvlib.irradiance.get_extra_radiation(times).set_axis(weather.index)
    poa = pvlib.irradiance.get_total_irradiance(
        panel["tilt"], panel["azimuth"], sun["apparent_zenith"], sun["azimuth"],
        weather["dni"], weather["ghi"], weather["dhi"], dni_extra=dni_extra, model="haydavies",
    )["poa_global"].clip(lower=0)
    t_cell = pvlib.temperature.faiman(poa, weather["temp_air"], weather["wind_speed"])
    p = pvlib.pvsystem.pvwatts_dc(poa, t_cell, 1.0, panel["gamma_pdc"]) * (1 - panel["system_loss"])
    ghi_clear = pvlib.clearsky.haurwitz(sun["apparent_zenith"])["ghi"]
    return pd.DataFrame({
        "sun_elevation": 90 - sun["apparent_zenith"], "sun_azimuth": sun["azimuth"],
        "poa": poa, "t_cell": t_cell, "p_pvlib": p.clip(lower=0),
        "clear_index": (weather["ghi"] / ghi_clear.where(ghi_clear > 20)).clip(upper=1.5),
    })
