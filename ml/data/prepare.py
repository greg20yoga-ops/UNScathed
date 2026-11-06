"""Unduh dan rapikan data evaluasi ke data/processed/. Jalankan: python -m ml.prepare"""
import zipfile
from pathlib import Path

import requests

from .battery import load_npz
from .config import PROCESSED_DIR, ROOT, load_config
from .lareunion import hourly_electrical, hourly_sensor
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
        load_npz(path).round(3).to_csv(PROCESSED_DIR / f"bboxx_{label}_hourly.csv")


def main():
    cfg = load_config()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for unit in cfg["units"]:
        hourly_electrical(unit).round(3).to_csv(PROCESSED_DIR / f"lareunion_{unit}_hourly.csv")
    hourly_sensor().to_csv(PROCESSED_DIR / "lareunion_sensor_hourly.csv")
    weather = fetch_history(cfg["site"], "2021-10-01", "2023-04-14")
    weather.to_csv(PROCESSED_DIR / "lareunion_weather_hourly.csv")
    fetch_bboxx()


if __name__ == "__main__":
    main()
