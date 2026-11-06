"""Unduh dan rapikan data evaluasi ke data/processed/, lalu baca kembali."""
import zipfile
from pathlib import Path

import pandas as pd
import requests

from ..config import PROCESSED_DIR, ROOT
from ..features import assemble
from .sources import bboxx_hourly, lareunion_electrical, lareunion_sensor
from .weather import fetch_history

BBOXX_URL = "https://ora.ox.ac.uk/objects/uuid:e41d3d4c-f74e-4d76-81fd-0caa77ec6cec/files/"
BBOXX_FILES = {"meta_data.csv": "dtd96k277p", "set_10.zip": "d9g54xh85t"}
BBOXX_DEMO = {"sehat": 99, "melemah": 995}
RAW_BBOXX = ROOT / "data" / "raw" / "bboxx"


def fetch_bboxx():
    """Satu bagian data BBOXX (±80 MB, 27 baterai), cukup untuk uji aturan baterai."""
    RAW_BBOXX.mkdir(parents=True, exist_ok=True)
    for name, file_id in BBOXX_FILES.items():
        path = RAW_BBOXX / name
        if not path.exists():
            path.write_bytes(requests.get(BBOXX_URL + file_id, timeout=600).content)
    with zipfile.ZipFile(RAW_BBOXX / "set_10.zip") as archive:
        archive.extractall(RAW_BBOXX)
    for label, battery_id in BBOXX_DEMO.items():
        path = next(Path(RAW_BBOXX).rglob(f"{battery_id}.npz"))
        bboxx_hourly(path).round(3).to_csv(PROCESSED_DIR / f"bboxx_{label}_hourly.csv")


def prepare(cfg):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for unit in cfg["units"]:
        lareunion_electrical(unit).round(3).to_csv(PROCESSED_DIR / f"lareunion_{unit}_hourly.csv")
    lareunion_sensor().to_csv(PROCESSED_DIR / "lareunion_sensor_hourly.csv")
    weather = fetch_history(cfg["site"], "2021-10-01", "2023-04-14")
    weather.to_csv(PROCESSED_DIR / "lareunion_weather_hourly.csv")
    fetch_bboxx()


def load_processed(name):
    return pd.read_csv(PROCESSED_DIR / name, index_col="timestamp", parse_dates=True)


def load_unit(unit, cfg):
    hourly = load_processed(f"lareunion_{unit}_hourly.csv")
    hourly["p_actual"] = hourly["p_w"] / cfg["units"][unit]["capacity_w"]
    return assemble(hourly, load_processed("lareunion_weather_hourly.csv"), cfg["site"], cfg["panel"])


def split(frame, cfg):
    """Periode uji dipisahkan utuh, jadi model tidak pernah melihat cuaca periode uji."""
    tz = cfg["site"]["tz"]
    start, end = (pd.Timestamp(cfg["split"][k], tz=tz) for k in ("test_start", "test_end"))
    in_test = (frame.index >= start) & (frame.index < end)
    return frame[~in_test], frame[in_test]
