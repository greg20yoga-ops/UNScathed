"""Ringkasan, grafik, dan laporan evaluasi."""
import matplotlib
import numpy as np
import pandas as pd

from ..config import ROOT
from . import faults

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, ORANGE, RED, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#e34948", "#0b0b0b", "#52514e", "#e6e5e1"
METHOD_NAMES = {
    "threshold_20": "Threshold tetap 20%",
    "threshold_adil": "Threshold tetap, alarm palsu disamakan",
    "dua_jam": "pvlib + XGBoost, aturan 2 jam",
    "pvlib": "pvlib + CUSUM",
    "usulan": "pvlib + XGBoost + CUSUM (usulan)",
    "tetangga": "Pembanding unit tetangga + CUSUM",
    "sensor": "Sensor di lokasi + CUSUM (batas atas)",
}


def summarize(events, fa, real):
    recall = events.pivot_table(index="method", columns="pattern", values="detected", aggfunc="mean")
    delay = events.groupby("method")["delay_h"].median().rename("delay_median_jam")
    shading = real.groupby("method")["detected"].mean().rename("bayangan_nyata")
    table = fa.set_index("method").join(recall).join(shading).join(delay)
    return table.reindex(METHOD_NAMES).rename(index=METHOD_NAMES)


def plot_comparison(test, expected, detectors, cfg, path):
    """Atas: mendung tanpa gangguan. Bawah: panel kotor tersuntik."""
    rng = np.random.default_rng(cfg["faults"]["seed"])
    tz, panel_w = cfg["site"]["tz"], cfg["rupiah"]["panel_w"]
    fn_base, fn_ours = detectors["threshold_20"], detectors["usulan"]

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


def write_report(table, events, real, batt, accuracy, stored, test):
    scenario = events[events["method"].isin(["usulan", "tetangga"])].groupby(["pattern", "variant", "method"]).agg(
        kejadian=("detected", "size"), terdeteksi=("detected", "sum"), delay_median_jam=("delay_h", "median"),
        penyebab_benar=("cause_ok", "mean")).reset_index().round(2)
    real_table = real[real["method"].isin(["threshold_adil", "usulan", "tetangga"])].groupby(["code", "method"]).agg(
        hari=("detected", "size"), terdeteksi=("detected", "sum")).reset_index()
    repaired = batt[batt["repaired"]]
    lines = [
        "# Hasil evaluasi (dibuat otomatis oleh `python -m ml evaluate`)", "",
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
