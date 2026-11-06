"""Pintu masuk ML untuk kode lain (penjadwal, FastAPI, skrip). Data masuk dan keluar sebagai tabel."""
import pandas as pd

from .config import load_config
from .data.sources import telemetry_hourly
from .data.weather import fetch_history, fetch_recent
from .detection.pipeline import score_unit
from .features import assemble
from .model import load_artifact, train_site


def _hourly_by_unit(readings, cfg):
    hourly = telemetry_hourly(readings, cfg["rupiah"]["panel_w"])
    if hourly.empty:
        raise ValueError("tidak ada telemetri yang valid")
    return hourly.groupby("unit_id")


def score(readings, site, weather=None):
    """Telemetri mentah (riwayat 8+ hari) -> baris kontrak v1 per unit per jam. Tanpa status."""
    cfg = load_config(site)
    artifact = load_artifact(site)
    weather = fetch_recent(cfg["site"]) if weather is None else weather
    rows = [score_unit(assemble(hourly.drop(columns="unit_id"), weather, cfg["site"], cfg["panel"]),
                       artifact, cfg, unit_id, "iot")
            for unit_id, hourly in _hourly_by_unit(readings, cfg)]
    return pd.concat(rows, ignore_index=True)


def train(readings, site, weather=None):
    """Latih model lokasi dari 2-4 minggu telemetri normal satu unit. Hasil dipakai otomatis oleh score()."""
    cfg = load_config(site)
    units = list(_hourly_by_unit(readings, cfg))
    if len(units) != 1:  # shortcut: satu unit acuan per lokasi, gabungkan unit kalau data satu unit kurang
        raise ValueError("latih dengan telemetri satu unit acuan")
    hourly = units[0][1].drop(columns="unit_id")
    if weather is None:
        weather = fetch_history(cfg["site"], hourly.index.min().date().isoformat(), hourly.index.max().date().isoformat())
    return train_site(assemble(hourly, weather, cfg["site"], cfg["panel"]), cfg, site)
