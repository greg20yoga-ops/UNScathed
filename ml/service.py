"""Skor telemetri alat IoT menjadi file kontrak. Jalankan tiap jam:

    python -m ml.score --telemetry telemetri.csv --site ml/situs_contoh.yaml

telemetri.csv cukup berisi riwayat 8+ hari. Kontrak kolomnya: docs/kontrak_telemetri.md
"""
import argparse

import pandas as pd

from .config import ROOT, load_config
from .features import assemble
from .monitor import load_artifact, score_unit
from .telemetry import to_hourly
from .weather import fetch_recent


def score_telemetry(readings, weather, cfg, site_cfg, artifact):
    """Semua unit pada telemetri -> baris kontrak. Unit baru memakai pvlib saja sampai dilatih."""
    panel_w, merged = site_cfg["rupiah"]["panel_w"], {**cfg, **site_cfg}
    rows = []
    for unit_id, hourly in to_hourly(readings, panel_w).groupby("unit_id"):
        frame = assemble(hourly.drop(columns="unit_id"), weather, merged["site"], merged["panel"])
        rows.append(score_unit(frame, artifact, merged, unit_id, "iot"))
    return pd.concat(rows, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--telemetry", required=True)
    ap.add_argument("--site", required=True, help="YAML lokasi dan panel, lihat ml/situs_contoh.yaml")
    ap.add_argument("--out", default=ROOT / "output" / "hasil_deteksi.csv")
    args = ap.parse_args()
    cfg, site_cfg = load_config(), load_config(args.site)
    weather = fetch_recent(site_cfg["site"])
    result = score_telemetry(pd.read_csv(args.telemetry), weather, cfg, site_cfg, load_artifact("weather_pvlib"))
    result.to_csv(args.out, index=False)
    print(f"{len(result)} baris -> {args.out}")


if __name__ == "__main__":
    main()
