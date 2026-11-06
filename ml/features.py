"""Satukan produksi aktual + cuaca + fisika pvlib menjadi satu tabel analisis per jam."""
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


def assemble(hourly, weather, site, panel):
    """hourly butuh kolom p_actual. Jam tanpa cuaca dibuang: tidak ada dasar untuk menilainya."""
    complete = weather.dropna(subset=["ghi", "dni", "dhi", "temp_air", "wind_speed"])
    joined = hourly.join(complete, how="inner").join(estimate(complete, site, panel))
    return joined.sort_index()


def peer_expected(frame, peer, scale=1.0):
    """Unit tetangga sebagai acuan: cuaca yang sama sudah tercermin di produksinya."""
    return peer["p_actual"].reindex(frame.index) * scale


def sensor_expected(frame, sensor, panel):
    """Batas atas: radiasi dan suhu terukur di lokasi. Alat murah di lapangan tidak punya sensor ini."""
    measured = sensor.reindex(frame.index)
    dc = pvlib.pvsystem.pvwatts_dc(measured["gti"], measured["tpv"], 1.0, panel["gamma_pdc"])
    return dc * (1 - panel["system_loss"])
