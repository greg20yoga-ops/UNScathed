"""Satukan produksi aktual + cuaca + fisika menjadi satu tabel analisis per jam."""
import pvlib

from .physics import estimate


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
