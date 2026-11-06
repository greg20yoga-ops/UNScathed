"""Perintah pipeline. Jalankan dari root repo: python -m ml <perintah>"""
import argparse

import pandas as pd

from .config import ROOT, load_config


def main():
    parser = argparse.ArgumentParser(prog="python -m ml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="unduh dan rapikan data evaluasi")
    commands.add_parser("train", help="latih model La Réunion")
    evaluate = commands.add_parser("evaluate", help="hasil, grafik, file dashboard")
    evaluate.add_argument("--tune", action="store_true", help="uji aturan penyebab di data latih saja")
    for name, text in (("score", "skor telemetri alat"), ("fit-site", "latih model lokasi dari telemetri normal")):
        command = commands.add_parser(name, help=text)
        command.add_argument("--telemetry", required=True)
        command.add_argument("--site", required=True, help="nama file di ml/sites/, tanpa .yaml")
    commands.choices["score"].add_argument("--out", default=ROOT / "output" / "hasil_deteksi.csv")
    args = parser.parse_args()

    # impor di sini supaya --help tidak memuat seluruh pustaka ML
    if args.command == "prepare":
        from .data.prepare import prepare
        prepare(load_config())
    elif args.command == "train":
        from .evaluation.run import run
        run("train")
    elif args.command == "evaluate":
        from .evaluation.run import run
        run("tune" if args.tune else "evaluate")
    elif args.command == "score":
        from .service import score
        result = score(pd.read_csv(args.telemetry), args.site)
        result.to_csv(args.out, index=False)
        print(f"{len(result)} baris -> {args.out}")
    else:
        from .service import train
        train(pd.read_csv(args.telemetry), args.site)
        print(f"model lokasi {args.site} tersimpan")


if __name__ == "__main__":
    main()
