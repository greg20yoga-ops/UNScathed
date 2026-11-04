"""Dashboard v0 (Yoga). Jalankan dari ROOT repo:
    streamlit run dashboard/app.py
Membaca keluaran model lewat dashboard/data.py (kontrak data v1 di README)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.data import SOURCE_TEXT, cause_text, episodes, load, needs_technician, rupiah

st.set_page_config(page_title="UNScathed · Pemantau PLTS", page_icon="☀️", layout="wide")


@st.cache_data(ttl=30)
def get_data():
    return load()


try:
    df, info = get_data()
except Exception as e:
    st.error(f"Gagal membaca keluaran model: {e}")
    st.stop()

st.title("UNScathed · Pemantau PLTS & Baterai")
st.caption("Alarm sadar-cuaca: produksi aktual dibandingkan dengan produksi seharusnya menurut cuaca.")

sources = sorted(df["data_source"].dropna().astype(str).unique())
if (df["data_label"] == "suntikan").any() or "sintetis" in sources:
    st.warning("**SIMULASI**: gangguan pada data ini disuntikkan buatan untuk pengujian. "
               "Sumber data: " + ", ".join(SOURCE_TEXT.get(s, s) for s in sources))
if info["mode"] == "lama":
    st.info("Membaca format lama `data/sim/output_*.csv` (dikonversi ke kontrak v1). "
            "Begitu `output/hasil_deteksi.csv` ada, file itu yang dipakai.")
for w in info["warnings"]:
    st.warning(w)

ep_all = episodes(df)
units = list(df["unit_id"].unique())

# ---------- ringkasan semua unit ----------
st.subheader("Semua unit")
last = df.groupby("unit_id").tail(1).set_index("unit_id")
summary = pd.DataFrame({
    "status": last["alarm"].map({1: "🔴 ALARM", 0: "🟢 Normal"}),
    "penyebab terakhir": ep_all.groupby("unit_id")["cause_guess"].last().map(cause_text) if len(ep_all) else "-",
    "kejadian alarm": ep_all.groupby("unit_id").size() if len(ep_all) else 0,
    "total rugi": df.groupby("unit_id")["loss_rp"].sum().map(rupiah),
}).reindex(units)
summary["kejadian alarm"] = summary["kejadian alarm"].fillna(0).astype(int)
summary["penyebab terakhir"] = summary["penyebab terakhir"].fillna("-")
st.dataframe(summary, width="stretch")

# ---------- pilih unit ----------
with st.sidebar:
    st.header("Pilih unit")
    with_alarm = [u for u in units if u in set(ep_all.get("unit_id", []))]
    unit = st.selectbox("Unit", units, index=units.index(with_alarm[0]) if with_alarm else 0)
    g = df[df["unit_id"] == unit]
    dmin, dmax = g["timestamp"].min().date(), g["timestamp"].max().date()
    ep_u = ep_all[ep_all["unit_id"] == unit] if len(ep_all) else ep_all
    default_start = max(dmin, (ep_u["mulai"].min() - pd.Timedelta(days=3)).date()) if len(ep_u) else dmin
    default_end = min(dmax, (pd.Timestamp(default_start) + pd.Timedelta(days=10)).date())
    rng = st.date_input("Rentang tanggal", (default_start, default_end), min_value=dmin, max_value=dmax)
    if st.button("Muat ulang data"):
        get_data.clear()
        st.rerun()
    st.caption(f"Sumber: `{Path(info['source']).relative_to(ROOT)}` · zona waktu {info['tz']}")

start, end = (rng if isinstance(rng, (list, tuple)) and len(rng) == 2 else (rng[0], rng[0]) if isinstance(rng, (list, tuple)) else (rng, rng))
w = g[(g["timestamp"].dt.date >= start) & (g["timestamp"].dt.date <= end)].copy()
w["waktu"] = w["timestamp"].dt.tz_localize(None)

st.subheader(f"Unit {unit}")
now = g.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Status (jam terakhir)", "ALARM" if now["alarm"] else "Normal")
c2.metric("Penyebab", cause_text(ep_u["cause_guess"].iloc[-1]) if len(ep_u) else "-")
c3.metric("Rugi pada rentang", rupiah(w["loss_rp"].sum()))
c4.metric("Kejadian alarm (semua)", len(ep_u))

# ---------- grafik aktual vs seharusnya ----------
lines = w.melt(id_vars="waktu", value_vars=["pv_actual_w", "pv_expected_w"], var_name="seri", value_name="daya_w")
lines["seri"] = lines["seri"].map({"pv_actual_w": "aktual", "pv_expected_w": "seharusnya (dari cuaca)"})


def bands(col, label):
    if col not in w or w[col].isna().all():
        return pd.DataFrame(columns=["mulai", "selesai", "jenis"])
    e = episodes(w, col)
    if e.empty:
        return pd.DataFrame(columns=["mulai", "selesai", "jenis"])
    end_val = w["timestamp"].max() + pd.Timedelta(hours=1)
    selesai = [(p if pd.notna(p) else end_val).tz_localize(None) for p in e["pulih"]]
    mulai = [m.tz_localize(None) for m in e["mulai"]]
    return pd.DataFrame({"mulai": mulai, "selesai": selesai, "jenis": label})


b_ai = bands("alarm", "Alarm sadar-cuaca")
ymax = float(max(w["pv_expected_w"].max(), w["pv_actual_w"].max(), 1)) * 1.05
base = alt.Chart(lines).mark_line().encode(
    x=alt.X("waktu:T", title=None),
    y=alt.Y("daya_w:Q", title="daya (W)", scale=alt.Scale(domain=[0, ymax])),
    color=alt.Color("seri:N", title=None, scale=alt.Scale(range=["#1f77b4", "#2ca02c"])),
    strokeDash=alt.condition(alt.datum.seri == "aktual", alt.value([1, 0]), alt.value([5, 4])),
    tooltip=["waktu:T", "seri:N", alt.Tooltip("daya_w:Q", format=".1f")],
)
chart = base
if not b_ai.empty:
    shade = alt.Chart(b_ai).mark_rect(opacity=0.18, color="red").encode(x="mulai:T", x2="selesai:T")
    chart = shade + base
st.altair_chart(chart.properties(height=320), width="stretch")

# ---------- perbandingan alarm biasa vs sadar-cuaca ----------
b_th = bands("alarm_threshold", "Alarm biasa (ambang tetap)")
if not w["alarm_threshold"].isna().all():
    st.markdown("**Alarm biasa vs alarm sadar-cuaca** (merah = alarm berbunyi)")
    strip = pd.concat([b_th, b_ai], ignore_index=True)
    if strip.empty:
        st.caption("Tidak ada alarm pada rentang ini.")
    else:
        st.altair_chart(alt.Chart(strip).mark_bar(color="#d62728", height=18).encode(
            x=alt.X("mulai:T", title=None, scale=alt.Scale(domain=[w["waktu"].min(), w["waktu"].max()])),
            x2="selesai:T",
            y=alt.Y("jenis:N", title=None, sort=["Alarm biasa (ambang tetap)", "Alarm sadar-cuaca"]),
        ).properties(height=90), width="stretch")
    n_th, n_ai = len(episodes(g, "alarm_threshold")), len(ep_u)
    st.caption(f"Seluruh data unit ini: alarm biasa {n_th} kejadian, alarm sadar-cuaca {n_ai} kejadian.")

# ---------- baterai ----------
if w["batt_v"].notna().any():
    st.markdown("**Tegangan baterai** (celah = data baterai hilang)")
    st.altair_chart(alt.Chart(w).mark_line(color="#9467bd").encode(
        x=alt.X("waktu:T", title=None), y=alt.Y("batt_v:Q", title="V", scale=alt.Scale(zero=False))
    ).properties(height=160), width="stretch")
else:
    st.caption("Data baterai (`batt_v`) belum ada di keluaran model untuk unit ini.")

# ---------- log alarm ----------
st.subheader("Log alarm")
if ep_u.empty:
    st.write("Tidak ada alarm untuk unit ini.")
else:
    log = pd.DataFrame({
        "mulai": ep_u["mulai"].dt.strftime("%d %b %Y %H:%M"),
        "pulih": ep_u["pulih"].dt.strftime("%d %b %Y %H:%M").fillna("masih aktif"),
        "durasi (jam)": ep_u["durasi_jam"],
        "penyebab": ep_u["cause_guess"].map(cause_text),
        "butuh teknisi": ep_u["cause_guess"].map(needs_technician),
        "aktual / seharusnya": ep_u.apply(lambda r: f"{r.pv_actual_w:.1f} / {r.pv_expected_w:.1f} W", axis=1),
        "rugi kejadian": ep_u["rugi_kejadian_rp"].map(rupiah),
        "label": ep_u["data_label"].map({"suntikan": "SIMULASI", "nyata": "nyata"}),
    })
    st.dataframe(log, width="stretch", hide_index=True)

with st.expander("Data mentah unit ini"):
    st.dataframe(w.drop(columns="waktu"), width="stretch", hide_index=True)
    st.download_button("Unduh CSV", w.drop(columns="waktu").to_csv(index=False), f"{unit}.csv", "text/csv")
