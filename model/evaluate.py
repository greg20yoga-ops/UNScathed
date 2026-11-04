"""Evaluasi: 3 metode pada data yang sama.
   threshold (alarm biasa) | pvlib (selisih vs model fisik) | pvlib+ML (selisih vs model terkoreksi)
Pembagian data berdasarkan WAKTU; gangguan hanya disuntik ke bagian uji."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import ROOT, steps_per_hour
from .contract import to_contract
from .cause import guess_cause
from .detectors import threshold_detector, ratio_detector, episodes
from .fault_injection import inject
from .ml_residual import ResidualCorrector

METHODS = ["threshold", "pvlib", "pvlib_ml"]


def _scenarios(cfg):
    yield "no_fault", None, {}
    for pat, spec in cfg["faults"]["patterns"].items():
        for i, params in enumerate(spec["variants"], 1):
            yield f"{pat}_v{i}", pat, params


def _run_methods(d, cfg, sph, corr):
    d = d.copy()
    d["expected_ml_w"] = corr.expected_adj(d)
    th = threshold_detector(d, cfg, sph)
    a_pv, r_pv = ratio_detector(d, "expected_w", cfg, sph)
    a_ml, r_ml = ratio_detector(d, "expected_ml_w", cfg, sph)
    return d, {"threshold": th, "pvlib": a_pv, "pvlib_ml": a_ml}, {"pvlib": r_pv, "pvlib_ml": r_ml}


def _loss_rp(d, alarm, cfg, sph):
    r = cfg["rupiah"]
    lost_kwh = (d["expected_ml_w"] - d["pv_actual_w"]).clip(lower=0) / 1000.0 / sph
    loss = (lost_kwh * r["tarif_rp_per_kwh"]).where(alarm, 0.0)
    return loss


def evaluate(df, cfg, out_root=ROOT):
    sph = steps_per_hour(df.index)
    pdc0 = cfg["panel"]["pdc0_w"]
    gap = int(cfg["detector"]["episode_gap_h"] * sph)
    split = int(len(df) * cfg["data"]["train_frac"])
    train, test = df.iloc[:split], df.iloc[split:]
    corr = ResidualCorrector(cfg).fit(train)
    source = df.attrs.get("source", "?")
    test_days = (test.index[-1] - test.index[0]).days
    offset = min(cfg["faults"]["fault_start_offset_days"], max(3, test_days // 3))  # data pendek -> gangguan lebih awal
    fstart = (test.index[0] + pd.Timedelta(days=offset)).normalize()
    remain = test_days - offset
    print(f"[data] {source}\n[data] latih {train.index[0].date()}..{train.index[-1].date()} | "
          f"uji {test.index[0].date()}..{test.index[-1].date()} ({test_days} hari) | gangguan mulai {fstart.date()}")

    rows, outputs, nofault_pack = [], {}, None
    for name, pat, params in _scenarios(cfg):
        d0 = inject(test, pat, fstart, params, pdc0) if pat else test.assign(fault_label="none", fault_active=False)
        d, alarms, ratios = _run_methods(d0, cfg, sph, corr)
        if pat is None:
            nofault_pack = (d, alarms, ratios)
        cause = {}
        for m in METHODS:
            eps = episodes(alarms[m], gap)
            if pat is None:
                rows.append(dict(scenario=name, pattern="none", method=m, detected=np.nan, delay_h=np.nan,
                                 fa_episodes=len(eps), tp_episodes=np.nan, cause_ok=np.nan))
                continue
            pre = [e for e in eps if e[0] < fstart]
            win_d = min(cfg["faults"]["patterns"][pat].get("detect_window_days", cfg["detector"]["detect_window_days"]), remain)
            post = [e for e in eps if e[0] >= fstart and e[0] <= fstart + pd.Timedelta(days=win_d)]
            tp_all = [e for e in eps if e[0] >= fstart]
            det = len(post) > 0
            delay = (post[0][0] - fstart).total_seconds() / 3600 if det else np.nan
            ok = np.nan
            if m == "pvlib_ml" and det:
                g = guess_cause(d, ratios["pvlib_ml"], post[0][0], sph, cfg)
                ok = float(g == cfg["faults"]["patterns"][pat]["cause"])
            rows.append(dict(scenario=name, pattern=pat, method=m, detected=det, delay_h=delay,
                             fa_episodes=len(pre), tp_episodes=len(tp_all), cause_ok=ok))
        # file keluaran untuk dashboard (metode utama = pvlib_ml)
        a = alarms["pvlib_ml"]
        causes = pd.Series("", index=d.index, dtype=object)
        for s, e in episodes(a, gap):
            causes.loc[s:e] = guess_cause(d, ratios["pvlib_ml"], s, sph, cfg)
        out = pd.DataFrame({
            "pv_actual_w": d["pv_actual_w"], "pv_expected_w": d["expected_ml_w"],
            "pv_expected_raw_w": d["expected_w"], "ratio": ratios["pvlib_ml"],
            "alarm_threshold": alarms["threshold"], "alarm": a, "cause_guess": causes,
            "loss_rp": _loss_rp(d, a, cfg, sph), "scenario": name,
            "fault_label": d["fault_label"], "data_source": source})
        out.index.name = "timestamp"
        outputs[name] = to_contract(out.reset_index())

    res = pd.DataFrame(rows)
    sim = out_root / "data" / "sim"
    for name, o in outputs.items():
        o.to_csv(sim / f"output_{name}.csv", index=False)
    res.to_csv(out_root / "bukti" / "hasil_evaluasi.csv", index=False)
    summary = _summarize(res, nofault_pack, test, cfg, sph, gap, test_days, source)
    (out_root / "docs" / "hasil_evaluasi.md").write_text(summary, encoding="utf-8")
    _plots(nofault_pack, res, cfg, gap, out_root, source)
    return res


def _summarize(res, nofault_pack, test, cfg, sph, gap, test_days, source):
    d, alarms, _ = nofault_pack
    daily_e = d["poa_wm2"].resample("D").sum()
    cloudy = set(daily_e[daily_e <= daily_e.quantile(0.30)].index.date)
    rows = []
    fault = res[res.pattern != "none"]
    for m in METHODS:
        eps = episodes(alarms[m], gap)
        fa_week = len(eps) / max(test_days / 7, 1e-9)
        fa_cloudy = sum(1 for s, _ in eps if s.date() in cloudy)
        fm = fault[fault.method == m]
        prec = fm.tp_episodes.sum() / max(fm.tp_episodes.sum() + fm.fa_episodes.sum(), 1)
        rows.append(dict(metode=m, **{"alarm_palsu/minggu": round(fa_week, 2),
                                      "presisi_alarm": round(prec, 2),
                                      "alarm_palsu_hari_mendung": fa_cloudy,
                                      "recall": round(fm.detected.astype(float).mean(), 2),
                                      "median_delay_jam": round(fm.delay_h.median(), 1)}))
    t1 = pd.DataFrame(rows).to_markdown(index=False)
    pv = fault[fault.method == "pvlib_ml"]
    t2 = fault.pivot_table(index="pattern", columns="method", values="detected", aggfunc="mean").round(2)[METHODS].to_markdown()
    t3 = pv.groupby("pattern")["cause_ok"].mean().round(2).rename("akurasi_tebakan_penyebab").to_markdown()
    return f"""# Hasil evaluasi (dibuat otomatis oleh `python -m model.run`)

**Sumber data:** {source}

Gangguan **disuntikkan buatan** ke bagian uji (data publik tidak berlabel gangguan).
Pembagian latih/uji berdasarkan waktu. Hari mendung = 30% hari uji dengan energi POA terendah.

## Ringkasan per metode (tanpa gangguan = ukur alarm palsu; dengan gangguan = ukur deteksi)
{t1}

## Recall per pola gangguan
{t2}

## Akurasi tebakan penyebab (metode pvlib_ml)
{t3}

> Catatan jujur: bila `pvlib_ml` tidak lebih baik dari `pvlib`, laporkan apa adanya dan cari sebabnya.
"""


def _plots(nofault_pack, res, cfg, gap, out_root, source=""):
    d, alarms, _ = nofault_pack
    daily_e = d["poa_wm2"].resample("D").sum()
    cand = daily_e[daily_e > 0].sort_values()
    cloudy = cand.index[:max(3, int(len(cand) * 0.3))]
    th_days = {s.normalize() for s, _ in episodes(alarms["threshold"], gap)}
    pick = next((x for x in cloudy if x in th_days), cloudy[0])
    w = d[pick - pd.Timedelta(days=1): pick + pd.Timedelta(days=2)]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4), sharey=True)
    for a, (key, title) in zip(ax, [("threshold", "Alarm biasa (ambang tetap)"),
                                    ("pvlib_ml", "Alarm sadar-cuaca (aktual vs seharusnya)")]):
        a.plot(w.index, w["pv_actual_w"], label="aktual", color="tab:blue")
        a.plot(w.index, w["expected_ml_w"], label="seharusnya (dari cuaca)", color="tab:green", ls="--")
        al = alarms[key].reindex(w.index)
        a.fill_between(w.index, 0, w["expected_w"].max() * 1.05, where=al.values, color="red", alpha=0.25, label="ALARM")
        a.set_title(title); a.set_xlabel("waktu"); a.tick_params(axis="x", rotation=30)
    ax[0].set_ylabel("daya (W)"); ax[1].legend(loc="upper right")
    fig.suptitle(f"Data TANPA gangguan, hari mendung: alarm biasa vs alarm sadar-cuaca\nSumber data: {source}", fontsize=10)
    fig.tight_layout(); fig.savefig(out_root / "bukti" / "grafik_perbandingan.png", dpi=150); plt.close(fig)

    fault = res[res.pattern != "none"]
    fa = res[res.pattern == "none"].set_index("method")["fa_episodes"].reindex(METHODS)
    rec = fault.groupby("method")["detected"].apply(lambda s: s.astype(float).mean()).reindex(METHODS)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ax[0].bar(METHODS, fa.values, color=["tab:red", "tab:orange", "tab:green"]); ax[0].set_title("Kejadian alarm palsu (data tanpa gangguan)", fontsize=9)
    ax[1].bar(METHODS, rec.values, color=["tab:red", "tab:orange", "tab:green"]); ax[1].set_ylim(0, 1.05); ax[1].set_title("Recall (gangguan suntikan terdeteksi)", fontsize=9)
    fig.suptitle(f"Sumber data: {source}", fontsize=8)
    fig.tight_layout(); fig.savefig(out_root / "bukti" / "grafik_metrik.png", dpi=150); plt.close(fig)
