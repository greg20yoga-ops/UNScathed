"""Alur penuh pada data evaluasi: latih, uji, lalu tulis hasil."""
import numpy as np
import pandas as pd

from .. import model
from ..config import DEFAULT_SITE, ROOT, load_config
from ..data.prepare import load_processed, load_unit, split
from ..detection.pipeline import detect
from ..features import peer_expected, sensor_expected
from .demo import demo_file
from .experiments import battery_check, build_detectors, false_alarms, real_shading, run_injections
from .report import plot_comparison, summarize, write_report


def train(cfg):
    """Latih di inverter 2 tanpa periode uji. Inverter 1 dan sensor hanya jadi acuan pembanding."""
    frame, _ = split(load_unit("inv2", cfg), cfg)
    peer, _ = split(load_unit("inv1", cfg), cfg)
    references = {"peer": peer_expected(frame, peer),
                  "sensor": pd.Series(sensor_expected(frame, load_processed("lareunion_sensor_hourly.csv"), cfg["panel"]),
                                      index=frame.index)}
    return model.train_site(frame, cfg, DEFAULT_SITE, references)


def tune_rules(cfg):
    """Uji aturan penyebab pada suntikan di data latih, supaya data uji tetap tidak tersentuh."""
    stored = model.load_calibration(DEFAULT_SITE)
    train_frame, _ = split(load_unit("inv2", cfg), cfg)
    day = train_frame[train_frame["sun_elevation"] >= cfg["detector"]["min_sun_elevation"]]
    oof = model.out_of_fold(day, stored["params"], cfg["model"]["n_folds"])
    detectors = {"usulan": lambda f: detect(f, oof, stored["weather_xgb"], cfg)["alarm"]}
    events = run_injections(day, detectors, {"usulan": (oof, stored["weather_xgb"])}, cfg)
    print(events.groupby("pattern")[["detected", "cause_ok"]].mean().round(2))
    print(pd.crosstab(events["pattern"], events["cause"]))


def evaluate(cfg):
    stored = model.load_calibration(DEFAULT_SITE)
    artifact = model.load_artifact(DEFAULT_SITE)
    _, test = split(load_unit("inv2", cfg), cfg)
    _, test_peer = split(load_unit("inv1", cfg), cfg)
    sensor = load_processed("lareunion_sensor_hourly.csv")
    expected = model.expected(test, artifact.model)

    detectors = build_detectors(test, test_peer, sensor, stored, artifact.model, cfg)
    cause_refs = {"usulan": (expected, stored["weather_xgb"]),
                  "tetangga": (peer_expected(test, test_peer).to_numpy(), stored["peer"])}
    events = run_injections(test, detectors, cause_refs, cfg)
    fa = false_alarms(test, detectors)
    real = real_shading(test_peer, test, build_detectors(test_peer, test, sensor, stored, artifact.model, cfg), cfg)

    min_elev = cfg["detector"]["min_sun_elevation"]
    accuracy = {name: {"mae": float(np.abs(test["p_actual"] - p).where(test["sun_elevation"] >= min_elev).mean())}
                for name, p in {"pvlib": test["p_pvlib"], "pvlib + XGBoost": expected}.items()}
    table = summarize(events, fa, real)

    (ROOT / "bukti").mkdir(exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)
    events.to_csv(ROOT / "bukti" / "hasil_evaluasi.csv", index=False)
    demo_file(test, test_peer, artifact, cfg).to_csv(ROOT / "output" / "hasil_deteksi.csv", index=False)
    plot_comparison(test, pd.Series(expected, index=test.index), detectors, cfg, ROOT / "bukti" / "grafik_perbandingan.png")
    write_report(table, events, real, battery_check(cfg), accuracy, stored, test)
    print(table.round(2).T.to_string())


def run(step):
    {"train": train, "tune": tune_rules, "evaluate": evaluate}[step](load_config(DEFAULT_SITE))
