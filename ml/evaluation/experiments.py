"""Percobaan evaluasi: tiap detektor diadu pada data yang sama."""
import numpy as np
import pandas as pd

from ..config import ROOT
from ..data.prepare import fetch_bboxx
from ..data.sources import bboxx_hourly
from ..detection import battery, causes, detector
from ..detection.pipeline import detect
from ..features import peer_expected, sensor_expected
from ..model import expected as model_expected
from ..schema import FAULT_CAUSE
from . import faults


def build_detectors(frame, peer, sensor, stored, model, cfg):
    """Tiap detektor: tabel ber-p_actual -> alarm per jam. Acuan dihitung sekali karena cuaca tetap."""
    d, tz = cfg["detector"], cfg["site"]["tz"]

    def cusum_on(expected, calibration):
        return lambda f: detect(f, expected, calibration, cfg)["alarm"]

    xgb = model_expected(frame, model)

    def two_hours(f):
        s = pd.Series(xgb, index=f.index)
        e = detector.deficit(f["p_actual"], s, detector.assessable(f, s, d))
        return detector.consecutive(e.dropna() > stored["weather_xgb"]["tau_p99"], 2).reindex(f.index, fill_value=False)

    return {
        "threshold_20": lambda f: detector.threshold_alarm(f, tz, d["threshold_frac"], d["threshold_hours"]),
        "threshold_adil": lambda f: detector.threshold_alarm(f, tz, stored["threshold_fair_frac"], d["threshold_hours"]),
        "dua_jam": two_hours,
        "pvlib": cusum_on(frame["p_pvlib"].to_numpy(), stored["weather_pvlib"]),
        "usulan": cusum_on(xgb, stored["weather_xgb"]),
        "tetangga": cusum_on(peer_expected(frame, peer).to_numpy(), stored["peer"]),
        "sensor": cusum_on(sensor_expected(frame, sensor, cfg["panel"]).to_numpy(), stored["sensor"]),
    }


def cause_of(fault_frame, expected, calibration, cfg, at):
    out = detect(fault_frame, expected, calibration, cfg)
    return causes.guess(out.loc[at - pd.Timedelta(days=cfg["causes"]["history_days"]):at], cfg["causes"], cfg["site"]["tz"])


def run_injections(frame, detectors, cause_refs, cfg):
    """Tiap kejadian dinilai terhadap salinan bersih: alarm yang memang ada tanpa gangguan tidak dihitung."""
    rng = np.random.default_rng(cfg["faults"]["seed"])
    clean = {name: fn(frame) for name, fn in detectors.items()}
    rows = []
    for pattern, variants in cfg["faults"]["variants"].items():
        for v, params in enumerate(variants, 1):
            for event, start in enumerate(faults.event_starts(frame, params["days"], cfg, rng, cfg["faults"]["n_events"])):
                faulty, hit = faults.PATTERNS[pattern](frame, start, cfg, rng, **params)
                window = (frame.index >= start) & (frame.index < start + pd.Timedelta(days=params["days"]))
                first_hit = frame.index[hit][0]
                for name, fn in detectors.items():
                    new = fn(faulty) & ~clean[name]
                    hits = frame.index[new.to_numpy() & window]
                    row = {"pattern": pattern, "variant": v, "event": event, "method": name, "detected": len(hits) > 0,
                           "delay_h": (hits[0] - first_hit).total_seconds() / 3600 if len(hits) else np.nan}
                    if name in cause_refs and len(hits):
                        guess = cause_of(faulty, *cause_refs[name], cfg, hits[0])
                        row["cause_ok"] = guess == FAULT_CAUSE[pattern]
                        row["cause"] = guess
                    rows.append(row)
    return pd.DataFrame(rows)


def false_alarms(frame, detectors, threshold_mendung=0.6):
    """Alarm palsu per minggu pada data tanpa gangguan, dipisah hari cerah dan mendung."""
    day = frame.index.strftime("%Y-%m-%d")
    cloudy = frame.groupby(day)["clear_index"].transform("mean").lt(threshold_mendung)
    rows = []
    for name, fn in detectors.items():
        alarm = fn(frame)
        onset = alarm & ~alarm.shift(fill_value=False)
        rows.append({"method": name, "alarm_palsu_per_minggu": detector.false_alarm_rate(alarm),
                     "per_minggu_cerah": onset[~cloudy].sum() / detector.weeks_covered(frame.index[~cloudy]),
                     "per_minggu_mendung": onset[cloudy].sum() / detector.weeks_covered(frame.index[cloudy])})
    return pd.DataFrame(rows)


def real_shading(frame, control, detectors, cfg):
    """Bayangan nyata di inverter 1. Inverter 2 (cuaca sama, tanpa gangguan) jadi pembanding alarm latar."""
    tz = cfg["site"]["tz"]
    day = frame.index.tz_convert(tz).strftime("%Y-%m-%d")
    rows = []
    for name, fn in detectors.items():
        new = fn(frame) & ~fn(control).reindex(frame.index, fill_value=False)
        for date, hours in frame[frame["fault_code"] > 0].groupby(day[frame["fault_code"] > 0]):
            code = hours["fault_code"].round(1).mode().iloc[0]
            rows.append({"method": name, "date": date, "code": code, "hours": len(hours),
                         "detected": bool(new[hours.index].any())})
    return pd.DataFrame(rows)


def battery_check(cfg):
    """Aturan sag pada baterai nyata: berapa yang tertangkap sebelum masuk perbaikan."""
    b, raw = cfg["battery"], ROOT / "data" / "raw" / "bboxx"
    if not raw.exists():
        fetch_bboxx()
    meta = pd.read_csv(raw / "meta_data.csv").set_index("ID")
    rows = []
    for path in sorted(raw.rglob("*.npz")):
        info = meta.loc[int(path.stem)]
        end = pd.Timestamp(info["ACTIVATED"], tz="UTC") + pd.Timedelta(days=int(info["Lifetime"]))
        hourly = bboxx_hourly(path).loc[:end]
        flags = battery.weak_flags(hourly, b["recent_days"], b["weak_sag_v_per_ah"])
        rows.append({"battery": path.stem, "repaired": not info["STILL_ALIVE"], "flagged": bool(flags.any()),
                     "flagged_last_30d": bool(flags.loc[end - pd.Timedelta(days=30):].any())})
    return pd.DataFrame(rows)
