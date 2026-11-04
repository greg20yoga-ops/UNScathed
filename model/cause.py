"""Tebakan penyebab BERBASIS ATURAN (bukan ML) pada tiap kejadian alarm.
Aturan sederhana & bisa dijelaskan ke juri; akurasinya dilaporkan per pola di evaluasi."""
import numpy as np
import pandas as pd


def guess_cause(df, ratio, t0, sph, cfg):
    pdc0 = cfg["panel"]["pdc0_w"]
    near = ratio[t0 - pd.Timedelta(hours=6): t0 + pd.Timedelta(hours=12)].dropna()
    if len(near) >= 3 and near.median() < 0.15:
        return "kabel_putus"

    win = df[t0 - pd.Timedelta(hours=12): t0 + pd.Timedelta(hours=24)]
    r = ratio.reindex(win.index)
    ok = r.notna() & (win["expected_w"] > 0.3 * pdc0)
    if ok.sum() >= 4:
        a, e = win.loc[ok, "pv_actual_w"], win.loc[ok, "expected_w"]
        top = e >= e.quantile(0.4)
        cv = lambda x: x.std() / max(x.mean(), 1e-6)
        if top.sum() >= 3 and cv(a[top]) < 0.08 and cv(e[top]) > 0.10 and r[ok].median() < 0.85:
            return "inverter_derating"

    byh = r.dropna().groupby(r.dropna().index.hour).median()
    if len(byh) >= 4 and (byh.max() - byh.min()) > 0.25 and (byh < 0.8).mean() <= 0.6:
        return "teduhan_sebagian"

    daily = ratio[t0 - pd.Timedelta(days=7): t0].dropna()
    daily = daily.groupby(daily.index.date).median()
    if len(daily) >= 4:
        slope = np.polyfit(np.arange(len(daily)), daily.values, 1)[0]
        if slope < -0.004:
            return "panel_kotor"
    return "tidak_diketahui"
