"""Bot Telegram (Yoga): kirim notifikasi saat alarm berubah 0 -> 1 (dan opsional "pulih" saat 1 -> 0).

Siapkan sekali:
  1. Buat bot lewat @BotFather -> dapat TELEGRAM_BOT_TOKEN
  2. Tambahkan bot ke grup, kirim satu pesan, buka https://api.telegram.org/bot<TOKEN>/getUpdates -> ambil chat.id
  3. Salin .env.example menjadi .env lalu isi keduanya (.env TIDAK di-commit)

Pakai (dari ROOT repo):
  python -m dashboard.telegram_bot --dry-run                    # tampilkan pesan saja, tidak mengirim
  python -m dashboard.telegram_bot --test                       # kirim satu pesan uji
  python -m dashboard.telegram_bot --unit PJU-demo-cable_cut_v1 --max 1
  python -m dashboard.telegram_bot --pulih --delay 3            # untuk rekaman demo
"""
import argparse
import os
import sys
import time

import requests

from dashboard.data import ROOT, cause_text, episodes, load, needs_technician, rupiah


def read_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return {k: os.environ.get(k) or env.get(k, "") for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}


def fmt_time(ts):
    return ts.strftime("%d %b %Y %H:%M ") + (ts.tzname() or "")


def msg_alarm(e):
    sim = "\n<i>SIMULASI: gangguan buatan untuk pengujian</i>" if e["data_label"] == "suntikan" else ""
    return (f"🚨 <b>ALARM</b> · {e['unit_id']}\n"
            f"Waktu: {fmt_time(e['mulai'])}\n"
            f"Penyebab: {cause_text(e['cause_guess'])}\n"
            f"Butuh teknisi: {needs_technician(e['cause_guess'])}\n"
            f"Produksi: {e['pv_actual_w']:.1f} W (seharusnya {e['pv_expected_w']:.1f} W)\n"
            f"Rugi sejauh ini: {rupiah(e['rugi_sejauh_ini_rp'])}{sim}")


def msg_recovered(e):
    return (f"✅ <b>PULIH</b> · {e['unit_id']}\n"
            f"Waktu: {fmt_time(e['pulih'])}\n"
            f"Lama gangguan: {e['durasi_jam']} jam\n"
            f"Rugi selama gangguan: {rupiah(e['rugi_kejadian_rp'])}")


def send(token, chat_id, text):
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=15)
    if not r.ok:
        raise RuntimeError(f"Telegram menolak ({r.status_code}): {r.text}")


def main():
    ap = argparse.ArgumentParser(description="Notifikasi alarm ke Telegram dari keluaran model")
    ap.add_argument("--dry-run", action="store_true", help="tampilkan pesan, jangan kirim")
    ap.add_argument("--test", action="store_true", help="kirim satu pesan uji lalu keluar")
    ap.add_argument("--unit", action="append", help="hanya unit ini (boleh diulang)")
    ap.add_argument("--pulih", action="store_true", help="kirim juga pesan saat alarm padam")
    ap.add_argument("--max", type=int, default=5, help="batas jumlah pesan (default 5)")
    ap.add_argument("--delay", type=float, default=1.0, help="jeda antar pesan, detik")
    a = ap.parse_args()

    cfg = read_env()
    if not a.dry_run and not (cfg["TELEGRAM_BOT_TOKEN"] and cfg["TELEGRAM_CHAT_ID"]):
        sys.exit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diisi di .env (lihat .env.example), "
                 "atau pakai --dry-run.")
    if a.test:
        send(cfg["TELEGRAM_BOT_TOKEN"], cfg["TELEGRAM_CHAT_ID"], "✅ Bot UNScathed tersambung.")
        print("Pesan uji terkirim.")
        return

    df, info = load()
    for w in info["warnings"]:
        print("PERINGATAN:", w)
    if a.unit:
        df = df[df["unit_id"].isin(a.unit)]
        if df.empty:
            sys.exit("Unit tidak ditemukan. Unit yang ada: " + ", ".join(load()[0]["unit_id"].unique()))

    events = []
    for _, e in episodes(df).iterrows():
        events.append((e["mulai"], msg_alarm(e)))
        if a.pulih and not e["masih_aktif"]:
            events.append((e["pulih"], msg_recovered(e)))
    events.sort(key=lambda x: x[0])
    print(f"{len(events)} kejadian ditemukan, mengirim {min(len(events), a.max)} "
          f"({'dry-run' if a.dry_run else 'Telegram'}).")

    for i, (_, text) in enumerate(events[:a.max]):
        if a.dry_run:
            print("-" * 40 + "\n" + text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
        else:
            send(cfg["TELEGRAM_BOT_TOKEN"], cfg["TELEGRAM_CHAT_ID"], text)
            print(f"terkirim {i + 1}")
        if i + 1 < min(len(events), a.max) and not a.dry_run:
            time.sleep(a.delay)


if __name__ == "__main__":
    main()
