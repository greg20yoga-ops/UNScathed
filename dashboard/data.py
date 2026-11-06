"""Baca file keluaran model sesuai KONTRAK DATA v1 (lihat README.md).

Dipakai oleh dashboard (app.py) dan bot Telegram (telegram_bot.py).
Urutan sumber:
  1. output/hasil_deteksi.csv          -> format kontrak v1 (dibuat ml/ Christian)
  2. data/sim/output_<skenario>.csv    -> format lama Christian, dikonversi ke kontrak v1 (sementara)
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = ROOT / "output" / "hasil_deteksi.csv"
LEGACY_DIR = ROOT / "data" / "sim"

REQUIRED = ["timestamp", "unit_id", "pv_actual_w", "pv_expected_w", "batt_v",
            "alarm", "cause_guess", "loss_rp", "data_label"]
OPTIONAL = ["batt_i_a", "alarm_threshold", "data_source", "fault_label"]

# nilai di file -> (teks untuk dashboard/Telegram, butuh teknisi?)
CAUSES = {
    "kabel_putus": ("Kabel putus / konektor lepas", "Ya"),
    "baterai_dicabut": ("Baterai dicabut / hilang", "Ya"),
    "panel_kotor": ("Panel kotor", "Tidak (cukup dibersihkan)"),
    "bayangan": ("Panel tertutup bayangan", "Tidak (pangkas/pindah)"),
    "konektor_kendor": ("Konektor kendor", "Ya"),
    "baterai_melemah": ("Baterai melemah", "Ya"),
    "inverter_derating": ("Inverter/controller membatasi daya", "Ya"),
    "tidak_diketahui": ("Gangguan, penyebab belum diketahui", "Cek lokasi"),
}
LEGACY_CAUSE = {"teduhan_sebagian": "bayangan"}

SOURCE_TEXT = {
    "sintetis": "SINTETIS (cuaca + produksi buatan)",
    "openmeteo": "Cuaca nyata Open-Meteo + produksi buatan",
    "kaggle": "Cuaca + produksi nyata (Kaggle)",
    "lareunion": "Produksi nyata La Réunion (diskalakan ke 50 Wp) + cuaca satelit",
    "iot": "Telemetri alat + cuaca satelit",
}


def site_tz():
    try:
        with open(ROOT / "config.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)["site"]["tz"]
    except Exception:
        return "Asia/Makassar"


def cause_text(code):
    code = "" if pd.isna(code) else str(code)
    return CAUSES.get(code, (code or "-", "-"))[0]


def needs_technician(code):
    code = "" if pd.isna(code) else str(code)
    return CAUSES.get(code, ("", "-"))[1]


def rupiah(x):
    return "Rp" + f"{float(x):,.0f}".replace(",", ".")


def _to01(s):
    return s.map(lambda v: 1 if str(v).strip().lower() in ("1", "1.0", "true") else 0).astype(int)


def _parse_ts(col, tz, warnings):
    col = col.astype(str)
    if col.str.contains(r"(?:[+-]\d\d:?\d\d|Z)$", regex=True).all():
        return pd.to_datetime(col, utc=True, format="ISO8601").dt.tz_convert(tz)
    warnings.append(f"timestamp tanpa zona waktu; dianggap waktu lokasi ({tz}).")
    return pd.to_datetime(col, format="ISO8601").dt.tz_localize(tz)


def _legacy_source(s):
    s = str(s).lower()
    if "sintetis" in s:
        return "sintetis"
    if "open" in s and "meteo" in s:
        return "openmeteo"
    if "kaggle" in s:
        return "kaggle"
    return s


def _from_contract(path, tz, warnings):
    d = pd.read_csv(path, dtype={"unit_id": str, "cause_guess": str, "data_label": str})
    missing = [c for c in REQUIRED if c not in d.columns]
    if missing:
        raise ValueError(f"{path.name} tidak sesuai kontrak data v1, kolom hilang: {', '.join(missing)}")
    d["timestamp"] = _parse_ts(d["timestamp"], tz, warnings)
    return d


def _from_legacy(paths, tz, warnings):
    d = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    fault = d["fault_label"].astype(str)
    return pd.DataFrame({
        "timestamp": _parse_ts(d["timestamp"], tz, []),
        "unit_id": "PJU-demo-" + d["scenario"].astype(str),
        "pv_actual_w": d["pv_actual_w"],
        "pv_expected_w": d["pv_expected_w"],
        "batt_v": np.nan,
        "batt_i_a": np.nan,
        "alarm": d["alarm"],
        "alarm_threshold": d["alarm_threshold"],
        "cause_guess": d["cause_guess"].fillna("").replace(LEGACY_CAUSE),
        "loss_rp": d["loss_rp"],
        "data_label": np.where(fault.eq("none"), "nyata", "suntikan"),
        "data_source": d["data_source"].map(_legacy_source),
        "fault_label": fault,
    })


def load():
    """Kembalikan (df, info). df sudah dinormalisasi ke kontrak v1."""
    tz, warnings = site_tz(), []
    if CONTRACT_FILE.exists():
        df, mode, src = _from_contract(CONTRACT_FILE, tz, warnings), "kontrak", CONTRACT_FILE
    else:
        paths = sorted(LEGACY_DIR.glob("output_*.csv"))
        if not paths:
            raise FileNotFoundError("Belum ada keluaran model: output/hasil_deteksi.csv atau data/sim/output_*.csv")
        df, mode, src = _from_legacy(paths, tz, warnings), "lama", LEGACY_DIR

    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = np.nan
    df["alarm"] = _to01(df["alarm"])
    if df["alarm_threshold"].notna().any():
        df["alarm_threshold"] = _to01(df["alarm_threshold"])
    df["cause_guess"] = df["cause_guess"].fillna("").astype(str)
    for c in ["pv_actual_w", "pv_expected_w", "batt_v", "batt_i_a", "loss_rp"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["loss_rp"] = df["loss_rp"].fillna(0.0)

    unknown = sorted(set(df["cause_guess"]) - set(CAUSES) - {""})
    if unknown:
        warnings.append("cause_guess di luar daftar kontrak: " + ", ".join(unknown))

    df = df.sort_values(["unit_id", "timestamp"]).reset_index(drop=True)
    return df, {"mode": mode, "source": src, "tz": tz, "warnings": warnings}


def episodes(df, col="alarm"):
    """Kejadian alarm per unit: deretan jam berturut-turut dengan col == 1."""
    rows = []
    for unit, g in df.groupby("unit_id", sort=False):
        g = g.reset_index(drop=True)
        a = g[col].fillna(0).astype(int).to_numpy()
        starts = np.flatnonzero(np.diff(np.r_[0, a]) == 1)
        ends = np.flatnonzero(np.diff(np.r_[a, 0]) == -1)
        for s, e in zip(starts, ends):
            seg = g.iloc[s:e + 1]
            causes = seg["cause_guess"][seg["cause_guess"] != ""]
            ongoing = e + 1 >= len(g)
            rows.append({
                "unit_id": unit,
                "mulai": seg["timestamp"].iloc[0],
                "pulih": pd.NaT if ongoing else g["timestamp"].iloc[e + 1],
                "durasi_jam": len(seg),
                "cause_guess": causes.mode().iloc[0] if len(causes) else "tidak_diketahui",
                "pv_actual_w": seg["pv_actual_w"].iloc[0],
                "pv_expected_w": seg["pv_expected_w"].iloc[0],
                "rugi_kejadian_rp": seg["loss_rp"].sum(),
                "rugi_sejauh_ini_rp": g["loss_rp"].iloc[:s + 1].sum(),
                "data_label": seg["data_label"].iloc[0],
                "masih_aktif": ongoing,
            })
    out = pd.DataFrame(rows)
    if len(out):
        tz = df["timestamp"].dt.tz
        out["pulih"] = pd.to_datetime(out["pulih"], utc=True).dt.tz_convert(tz)
    return out
