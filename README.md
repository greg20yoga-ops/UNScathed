# UNScathed

Pemantau murah untuk instalasi panel surya + baterai yang sudah terpasang (PJU surya, PLTS sekolah/puskesmas, UMKM).
UNS Innovation Hackathon 2026 · Subtema A · Ide v2 · Tim SEMPS (Yoga, Rafie, Bobi, Christian).

Model menebak produksi panel yang **seharusnya** dari cuaca. Alarm hanya berbunyi bila ada kerusakan (bukan karena
mendung), lalu muncul tebakan penyebab, rugi dalam rupiah, notifikasi Telegram, dan dashboard.
Untuk pendaftaran semuanya dibuktikan dengan **simulasi dan data publik**; alat fisik berupa rancangan.

## Isi repo

| Folder | Isi | Pemilik |
|---|---|---|
| `model/` | model produksi seharusnya, detektor, tebakan penyebab, evaluasi | Christian |
| `data/raw/`, `data/sim/` | data cuaca/PV mentah (tidak di-commit bila besar), data simulasi berlabel | Christian |
| `output/` | **`hasil_deteksi.csv`: file penghubung model → dashboard/bot** (kontrak di bawah) | Christian |
| `dashboard/` | dashboard Streamlit + bot Telegram | Yoga |
| `docs/` | keputusan, rupiah, sumber, pola gangguan, evaluasi, draf proposal | semua |
| `bukti/` | grafik, demo, tangkapan layar, skema rangkaian | semua |

## Menjalankan

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m model.run --source synthetic          # model Christian (data SINTETIS)
streamlit run dashboard/app.py                  # dashboard
python -m dashboard.telegram_bot --dry-run      # bot: lihat pesan tanpa mengirim
```

Bot Telegram butuh `.env` (salin dari `.env.example`, isi `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID`). Jangan commit `.env`.

---

## Kontrak data v1: `output/hasil_deteksi.csv`

Disepakati 4 Nov 2026, dari usulan Christian + tambahan Yoga.
**Mengubah nama kolom, satuan, atau daftar nilai wajib dikabari di grup dulu.**

- **Dibuat oleh:** model (Christian) · **Dibaca oleh:** dashboard + bot Telegram (Yoga)
- **Satu baris** = satu unit × satu jam · **urutan:** `unit_id`, lalu `timestamp` naik
- Desimal pakai titik. **Sel kosong = data tidak ada** (bukan nol). Encoding UTF-8, pemisah koma.

### Kolom wajib

| Kolom | Tipe | Satuan | Arti | Contoh |
|---|---|---|---|---|
| `timestamp` | ISO 8601 **dengan zona waktu** | — | **Akhir** jam yang dirangkum (11:00 = rata-rata 10:00–11:00). Zona waktu = `site.tz` di `config.yaml` | `2025-03-14T11:00:00+08:00` |
| `unit_id` | teks | — | Nama unit/skenario | `PJU-demo-kabel-putus` |
| `pv_actual_w` | angka | **W** | Produksi aktual panel (skala panel 50 Wp) | `0.0` |
| `pv_expected_w` | angka | **W** | Produksi seharusnya (panel sehat, cuaca saat itu) | `41.8` |
| `batt_v` | angka, boleh kosong | **V** | Tegangan baterai. Kosong = data baterai hilang | `12.6` |
| `alarm` | `0`/`1` | — | 1 = alarm sadar-cuaca menyala pada jam ini | `1` |
| `cause_guess` | teks dari daftar di bawah; kosong bila `alarm`=0 | — | Dugaan penyebab | `kabel_putus` |
| `loss_rp` | angka | **Rp** | Rugi **pada jam ini saja**. Total = jumlah kolom ini | `71.0` |
| `data_label` | `nyata` / `suntikan` | — | `suntikan` = gangguan di baris ini dibuat buatan untuk pengujian | `suntikan` |

### Kolom tambahan (boleh kosong, sangat disarankan)

| Kolom | Tipe | Satuan | Arti |
|---|---|---|---|
| `batt_i_a` | angka | **A** | Arus baterai. **Positif = mengisi (charging), negatif = membuang (discharging)** |
| `alarm_threshold` | `0`/`1` | — | Alarm biasa (ambang tetap) pada data yang sama, untuk grafik perbandingan |
| `data_source` | `sintetis` / `openmeteo` / `kaggle` | — | Asal cuaca + produksi. Beda dengan `data_label`: baris `nyata` bisa tetap memakai cuaca sintetis |
| `fault_label` | teks | — | Gangguan yang sebenarnya disuntikkan (`none` bila tidak ada). Hanya untuk demo/evaluasi |

### Daftar nilai `cause_guess`

| Nilai | Teks dashboard/Telegram | Butuh teknisi? |
|---|---|---|
| `kabel_putus` | Kabel putus / konektor lepas | Ya |
| `baterai_dicabut` | Baterai dicabut / hilang | Ya |
| `panel_kotor` | Panel kotor | Tidak (cukup dibersihkan) |
| `bayangan` | Panel tertutup bayangan | Tidak (pangkas/pindah) |
| `konektor_kendor` | Konektor kendor | Ya |
| `baterai_melemah` | Baterai melemah | Ya |
| `inverter_derating` | Inverter/controller membatasi daya | Ya |
| `tidak_diketahui` | Gangguan, penyebab belum diketahui | Cek lokasi |

### Aturan notifikasi

- Bot mengirim pesan saat `alarm` berubah **0 → 1** per unit (bukan tiap jam selama alarm menyala); opsional pesan "pulih" saat 1 → 0.
- Isi pesan: unit, jam, penyebab, butuh teknisi, aktual vs seharusnya, rugi sejauh ini, label SIMULASI bila `suntikan`.
- `loss_rp` boleh mulai dihitung sebelum alarm menyala (alarm menunggu beberapa jam berturut-turut agar tidak bunyi saat awan lewat).

### Contoh

```csv
timestamp,unit_id,pv_actual_w,pv_expected_w,batt_v,alarm,cause_guess,loss_rp,data_label,batt_i_a,alarm_threshold,data_source,fault_label
2025-03-14T10:00:00+08:00,PJU-demo-kabel-putus,39.2,40.1,13.1,0,,0.0,nyata,2.9,0,sintetis,none
2025-03-14T11:00:00+08:00,PJU-demo-kabel-putus,0.0,41.8,12.9,0,,71.0,suntikan,-0.4,1,sintetis,cable_cut
2025-03-14T12:00:00+08:00,PJU-demo-kabel-putus,0.0,43.0,12.8,1,kabel_putus,73.1,suntikan,-0.4,1,sintetis,cable_cut
2025-03-14T20:00:00+08:00,PJU-demo-baterai-dicabut,0.0,0.0,,1,baterai_dicabut,0.0,suntikan,,0,sintetis,battery_removed
```

Angka di contoh hanya ilustrasi.

### Status (4 Nov)

- [ ] Model masih menulis format lama (`data/sim/output_<skenario>.csv`: `scenario`, `True/False`, tanpa zona waktu, `teduhan_sebagian`).
      Dashboard sementara mengonversinya otomatis (`dashboard/data.py`); begitu `output/hasil_deteksi.csv` ada, file itu yang dipakai.
- [ ] Belum ada skenario baterai (`baterai_dicabut`, `baterai_melemah`) dan `batt_v`/`batt_i_a`.
- [ ] Lama tunggu alarm: samakan antara `consecutive_h` di `config.yaml` (sekarang 3 jam) dan dokumen ini.
- [ ] Lokasi + spesifikasi panel final: `docs/keputusan.md` → `site:`/`panel:` di `config.yaml`.
- [ ] Rumus rugi Rp final (Rafie, `docs/rupiah.md`) → `_loss_rp` di `model/evaluate.py`.
