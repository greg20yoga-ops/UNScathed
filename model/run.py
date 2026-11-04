"""Pakai:
  python -m model.run --source synthetic     # demo tanpa internet (SINTETIS)
  python -m model.run --source openmeteo     # cuaca nyata (jalankan scripts/fetch_weather.py dulu) + aktual sintetis
  python -m model.run --source kaggle        # aktual NYATA (taruh CSV di data/raw/kaggle/)
"""
import argparse
from .config import load_config
from . import data_sources as ds
from .evaluate import evaluate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synthetic", "openmeteo", "kaggle"], default="synthetic")
    ap.add_argument("--config", default=None)
    ap.add_argument("--days", type=int, default=120, help="hanya untuk synthetic")
    ap.add_argument("--plant", type=int, default=1, help="hanya untuk kaggle (1 atau 2)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.source == "synthetic":
        df = ds.load_synthetic(cfg, days=a.days)
    elif a.source == "openmeteo":
        df = ds.load_openmeteo(cfg)
    else:
        df = ds.load_kaggle(cfg, plant=a.plant)
    res = evaluate(df, cfg)
    print(open("docs/hasil_evaluasi.md", encoding="utf-8").read())


if __name__ == "__main__":
    main()
