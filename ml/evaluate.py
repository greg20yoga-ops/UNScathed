"""Evaluasi akhir + file demo dashboard. Jalankan: python -m ml.evaluate  (--tune = uji aturan di data latih)"""
import argparse
import json

import matplotlib
import numpy as np
import pandas as pd

from . import battery, causes, detector, faults, residual
from .config import ARTIFACT_DIR, PROCESSED_DIR, ROOT, load_config
from .features import peer_expected, sensor_expected
from .monitor import detect, load_artifact, score_unit
from .prepare import fetch_bboxx
from .schema import FAULT_CAUSE
from .train import load_sensor, load_unit, split

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, ORANGE, RED, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#e34948", "#0b0b0b", "#52514e", "#e6e5e1"
DEMO_START, DEMO_END = "2022-03-05", "2022-04-01"
METHOD_NAMES = {
    "threshold_20": "Threshold tetap 20%",
    "threshold_adil": "Threshold tetap, alarm palsu disamakan",
    "dua_jam": "pvlib + XGBoost, aturan 2 jam",
    "pvlib": "pvlib + CUSUM",
    "usulan": "pvlib + XGBoost + CUSUM (usulan)",
    "tetangga": "Pembanding unit tetangga + CUSUM",
    "sensor": "Sensor di lokasi + CUSUM (batas atas)",
}


def build_detectors(frame, peer, sensor, stored, model, cfg):
    """Tiap detektor: tabel ber-p_actual -> alarm per jam. Acuan dihitung sekali karena cuaca tetap."""
    d, tz = cfg["detector"], cfg["site"]["tz"]

    def cusum_on(expected, calibration):
        return lambda f: detect(f, expected, calibration, cfg)["alarm"]

    xgb = residual.expected(frame, model)

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
        hourly = battery.load_npz(path).loc[:end]
        flags = battery.weak_flags(hourly, b["recent_days"], b["weak_sag_v_per_ah"])
        rows.append({"battery": path.stem, "repaired": not info["STILL_ALIVE"], "flagged": bool(flags.any()),
                     "flagged_last_30d": bool(flags.loc[end - pd.Timedelta(days=30):].any())})
    return pd.DataFrame(rows)


def _aligned(trace, index, end):
    """Tempel rekaman baterai ke garis waktu unit: akhir rekaman jatuh pada waktu end."""
    shifted = trace.copy()
    shifted.index = end.ceil("h") - (trace.index.max() - trace.index)
    return shifted.reindex(index, method="nearest", tolerance=pd.Timedelta(minutes=30)).ffill().bfill()


def demo_file(test, control_peer, artifact, cfg):
    """Keluaran kontrak v1 untuk dashboard: satu unit per skenario pada periode uji."""
    read = lambda name: pd.read_csv(PROCESSED_DIR / name, index_col="timestamp", parse_dates=True)
    healthy, weak = read("bboxx_sehat_hourly.csv"), read("bboxx_melemah_hourly.csv")
    rng = np.random.default_rng(cfg["faults"]["seed"])
    start = pd.Timestamp("2022-03-08 09:00", tz=cfg["site"]["tz"])

    def unit(frame, unit_id, fault_label=None, history=None):
        return score_unit(frame, artifact, cfg, unit_id, "lareunion", fault_label, history)

    def with_battery(frame, trace=healthy, end=None):
        return frame.join(_aligned(trace, frame.index, frame.index.max() if end is None else end))

    def injected(pattern, params, unit_id):
        frame, hit = faults.PATTERNS[pattern](test, start, cfg, rng, **params)
        labels = pd.Series(np.where(hit, pattern, "none"), index=test.index)
        frame = with_battery(frame)
        if pattern == "cable_cut":  # panel lepas: aki tidak terisi, jadi tidak ikut rekaman aslinya
            frame.loc[hit, "batt_i_a"] = frame.loc[hit, "batt_i_a"].clip(upper=0)
            frame.loc[hit, "batt_v"] = frame.loc[hit, "batt_v"].clip(upper=12.8)
        return unit(frame, unit_id, labels)

    removed = with_battery(test)
    gone = removed.index >= start
    removed.loc[gone, ["batt_v", "batt_i_a"]] = np.nan
    variants = cfg["faults"]["variants"]
    weak_end = start + pd.Timedelta(days=20)
    weak_history = weak.set_axis(weak_end.ceil("h") - (weak.index.max() - weak.index))
    units = [
        unit(with_battery(test), "PJU-demo-normal"),
        injected("cable_cut", variants["cable_cut"][1], "PJU-demo-kabel-putus"),
        injected("soiling", variants["soiling"][2], "PJU-demo-panel-kotor"),
        injected("partial_shading", variants["partial_shading"][1], "PJU-demo-bayangan"),
        injected("loose_connector", variants["loose_connector"][1], "PJU-demo-konektor-kendor"),
        unit(removed, "PJU-demo-baterai-dicabut", pd.Series(np.where(gone, "battery_removed", "none"), index=test.index)),
        unit(with_battery(test, weak, weak_end), "PJU-demo-baterai-melemah", history=weak_history),
        unit(with_battery(control_peer), "PJU-bayangan-nyata"),
    ]
    out = pd.concat(units, ignore_index=True)
    return out[out["timestamp"].between(DEMO_START, DEMO_END)]


def summarize(events, fa, real):
    recall = events.pivot_table(index="method", columns="pattern", values="detected", aggfunc="mean")
    delay = events.groupby("method")["delay_h"].median().rename("delay_median_jam")
    shading = real.groupby("method")["detected"].mean().rename("bayangan_nyata")
    table = fa.set_index("method").join(recall).join(shading).join(delay)
    return table.reindex(METHOD_NAMES).rename(index=METHOD_NAMES)


def plot_comparison(test, control, detectors, cfg, path):
    """Atas: mendung tanpa gangguan. Bawah: panel kotor tersuntik."""
    rng = np.random.default_rng(cfg["faults"]["seed"])
    tz, panel_w = cfg["site"]["tz"], cfg["rupiah"]["panel_w"]
    fn_base, fn_ours = detectors["threshold_20"], detectors["usulan"]
    expected = pd.Series(residual.expected(test, load_artifact().model), index=test.index)

    base, ours = fn_base(test), fn_ours(test)
    local_days = test.index.tz_convert(tz).normalize()
    counts = pd.DataFrame({"base": base.to_numpy(), "ours": ours.to_numpy()}).groupby(local_days).sum()
    quiet = counts.rolling(3).sum()
    cloudy_end = quiet[quiet["ours"] == 0]["base"].idxmax()
    top = test.loc[cloudy_end - pd.Timedelta(days=2):cloudy_end + pd.Timedelta(days=1)]

    params = cfg["faults"]["variants"]["soiling"][2]
    best = None
    for start in faults.event_starts(test, params["days"], cfg, rng, 20):
        faulty, _ = faults.soiling(test, start, cfg, rng, **params)
        new = fn_ours(faulty) & ~ours
        if new.any() and not (fn_base(faulty) & ~base).any():
            best = (start, faulty)
            break
    start, faulty = best
    bottom = faulty.loc[start:start + pd.Timedelta(days=params["days"])]

    fig, axes = plt.subplots(2, 2, figsize=(11, 6.4), sharey=True, constrained_layout=True)
    panels = [(top, base, "Threshold tetap"), (top, ours, "Sadar-cuaca (usulan)"),
              (bottom, fn_base(faulty), "Threshold tetap"), (bottom, fn_ours(faulty), "Sadar-cuaca (usulan)")]
    rows = ["Mendung, panel sehat", "Panel kotor (suntikan)"]
    for i, (ax, (frame, alarm, title)) in enumerate(zip(axes.flat, panels)):
        # jam tanpa data (malam) dibiarkan kosong supaya garis tidak menyambung semu
        hours = pd.date_range(frame.index[0], frame.index[-1], freq="h")
        local = hours.tz_convert(tz).tz_localize(None)
        ax.plot(local, frame["p_actual"].reindex(hours) * panel_w, color=BLUE, lw=2, label="Produksi aktual")
        ax.plot(local, expected.reindex(hours) * panel_w, color=ORANGE, lw=2, label="Produksi seharusnya")
        on = alarm.reindex(hours).ffill().fillna(False).astype(bool).to_numpy()
        ax.fill_between(local, 0, 1, where=on, transform=ax.get_xaxis_transform(), color=RED, alpha=0.18, lw=0, label="Alarm")
        ax.set_title(f"{rows[i // 2]} · {title}: {'ALARM' if on.any() else 'tidak ada alarm'}", color=INK, fontsize=11, loc="left")
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(colors=MUTED, length=0, labelsize=9)
        ax.tick_params(axis="x", rotation=30)
    for ax in axes[:, 0]:
        ax.set_ylabel("Daya (W, skala panel 50 Wp)", color=MUTED, fontsize=10)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    alarm_patch = plt.Rectangle((0, 0), 1, 1, color=RED, alpha=0.18)
    fig.legend(handles[:2] + [alarm_patch], labels[:2] + ["Alarm"], loc="outside lower center", ncol=3, frameon=False, fontsize=10)
    fig.savefig(path, dpi=170, facecolor="#fcfcfb")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true", help="suntik ke data latih (out-of-fold), bukan data uji")
    tune = ap.parse_args().tune
    cfg = load_config()
    stored = json.loads((ARTIFACT_DIR / "calibration.json").read_text())
    artifact = load_artifact()
    inv2, inv1 = load_unit("inv2", cfg), load_unit("inv1", cfg)
    min_elev = cfg["detector"]["min_sun_elevation"]

    train, test = split(inv2, cfg)
    train_peer, test_peer = split(inv1, cfg)
    if tune:
        day = train[train["sun_elevation"] >= min_elev]
        oof = residual.out_of_fold(day, stored["params"], cfg["split"]["n_folds"])
        detectors = {"usulan": lambda f: detect(f, oof, stored["weather_xgb"], cfg)["alarm"]}
        events = run_injections(day, detectors, {"usulan": (oof, stored["weather_xgb"])}, cfg)
        print(events.groupby("pattern")[["detected", "cause_ok"]].mean().round(2))
        print(pd.crosstab(events["pattern"], events["cause"]))
        return

    sensor = load_sensor()
    detectors = build_detectors(test, test_peer, sensor, stored, artifact.model, cfg)
    cause_refs = {"usulan": (residual.expected(test, artifact.model), stored["weather_xgb"]),
                  "tetangga": (peer_expected(test, test_peer).to_numpy(), stored["peer"])}
    events = run_injections(test, detectors, cause_refs, cfg)
    fa = false_alarms(test, detectors)

    peer_for_real = build_detectors(test_peer, test, sensor, stored, artifact.model, cfg)
    real = real_shading(test_peer, test, peer_for_real, cfg)
    batt = battery_check(cfg)

    table = summarize(events, fa, real)
    accuracy = {m: {"mae": float(np.abs(test["p_actual"] - p).where(test["sun_elevation"] >= min_elev).mean())}
                for m, p in {"pvlib": test["p_pvlib"], "pvlib + XGBoost": residual.expected(test, artifact.model)}.items()}
    (ROOT / "bukti").mkdir(exist_ok=True)
    events.to_csv(ROOT / "bukti" / "hasil_evaluasi.csv", index=False)
    (ROOT / "output").mkdir(exist_ok=True)
    demo_file(test, test_peer, artifact, cfg).to_csv(ROOT / "output" / "hasil_deteksi.csv", index=False)
    plot_comparison(test, test_peer, detectors, cfg, ROOT / "bukti" / "grafik_perbandingan.png")
    write_report(table, events, real, batt, accuracy, stored, test)
    print(table.round(2).T.to_string())


def write_report(table, events, real, batt, accuracy, stored, test):
    scenario = events[events["method"].isin(["usulan", "tetangga"])].groupby(["pattern", "variant", "method"]).agg(
        kejadian=("detected", "size"), terdeteksi=("detected", "sum"), delay_median_jam=("delay_h", "median"),
        penyebab_benar=("cause_ok", "mean")).reset_index().round(2)
    real_table = real[real["method"].isin(["threshold_adil", "usulan", "tetangga"])].groupby(["code", "method"]).agg(
        hari=("detected", "size"), terdeteksi=("detected", "sum")).reset_index()
    repaired = batt[batt["repaired"]]
    lines = [
        "# Hasil evaluasi (dibuat otomatis oleh `python -m ml.evaluate`)", "",
        "**Data:** produksi nyata La Réunion (Okt 2021–Apr 2023), radiasi satelit SARAH3, suhu/angin ERA5.",
        f"**Periode uji:** Feb–Mei 2022 ({len(test)} jam, tidak dipakai melatih). Gangguan **disuntikkan**, kecuali baris bayangan nyata.",
        "", "## Akurasi produksi seharusnya (MAE per kapasitas, data uji)", "",
        pd.DataFrame(accuracy).T.round(4).to_markdown(),
        f"\nOut-of-fold data latih: pvlib {stored['mae_oof_pvlib']:.4f}, pvlib + XGBoost {stored['mae_oof_xgb']:.4f}.",
        "", "## Perbandingan detektor", "", table.round(2).T.to_markdown(),
        "", "Kolom pola = recall per kejadian. Alarm yang juga muncul di salinan tanpa gangguan tidak dihitung.",
        "", "## Hasil per skenario (untuk `docs/tabel_uji.md`)", "", scenario.to_markdown(index=False),
        "", "## Bayangan nyata per jenis label", "", real_table.to_markdown(index=False),
        "", "## Uji aturan baterai melemah (data nyata BBOXX, 27 baterai)", "",
        f"Baterai yang akhirnya masuk perbaikan dan tertandai dalam 30 hari terakhir: "
        f"{int(repaired['flagged_last_30d'].sum())} dari {len(repaired)}.",
        f"Baterai yang masih hidup dan tertandai: {int(batt[~batt['repaired']]['flagged'].sum())} dari {int((~batt['repaired']).sum())}.",
        "",
    ]
    (ROOT / "docs" / "hasil_evaluasi.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
