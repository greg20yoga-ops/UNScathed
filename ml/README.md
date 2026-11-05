# ML: alarm sadar-cuaca

Menilai apakah produksi panel menyimpang karena gangguan, bukan karena cuaca, lalu menebak penyebab dan rugi rupiahnya.
Hasil lengkap: `docs/hasil_evaluasi.md`. Rancangan dan keterbatasan: `docs/evaluasi.md`.

## Menjalankan (dari root repo)

```bash
pip install -r requirements.txt       # macOS: brew install libomp
python -m pytest ml/tests             # test, tanpa internet
python -m ml.evaluate                 # hasil, grafik, output/hasil_deteksi.csv
python -m ml.train                    # latih ulang (data olahan sudah ada di repo)
python -m ml.prepare                  # unduh ulang data mentah, ±30 menit
```

## Alur

```
cuaca satelit ─► physics.estimate ─► p_pvlib ─┐
      └───────── fitur ─► residual (XGBoost) ─┴► produksi seharusnya
telemetri alat ─► telemetry.to_hourly ─► produksi aktual ─┤
                                                          ▼
                 detector: kekurangan → z (derau per kondisi langit) → CUSUM → alarm
                                                          ▼
                 causes (aturan) → rupiah → baris kontrak v1 (monitor.score_unit)
```

| File | Tugas |
|---|---|
| `telemetry.py` | Pintu masuk alat IoT: validasi + rangkum per jam |
| `weather.py` | Open-Meteo: historis dan terbaru |
| `lareunion.py`, `battery.py` | Pembaca dataset |
| `physics.py` | Estimasi pvlib |
| `features.py` | Satukan aktual + cuaca + fisika; acuan tetangga dan sensor |
| `residual.py` | XGBoost: tuning, out-of-fold, prediksi |
| `detector.py` | Kekurangan, derau, CUSUM, threshold pembanding |
| `causes.py`, `rupiah.py` | Aturan penyebab, rugi per jam |
| `faults.py` | Generator gangguan untuk pengujian |
| `monitor.py` | **Satu jalur skor** untuk data historis dan IoT |
| `prepare.py`, `train.py`, `evaluate.py`, `score.py` | Perintah CLI |
| `config.yaml`, `situs_contoh.yaml` | Parameter evaluasi, parameter lokasi pasang |

## Integrasi IoT

Kontrak alat: `docs/kontrak_telemetri.md`. Tiap jam, server menjalankan:

```bash
python -m ml.score --telemetry telemetri.csv --site ml/situs_contoh.yaml
```

Skor tidak menyimpan status: cukup kirim riwayat 8+ hari, hasilnya file yang sama dengan yang dibaca dashboard.
Dari kode lain, panggil `ml.score.score_telemetry()`. Unit baru memakai pvlib saja sampai ada 2–4 minggu data normal di lokasi itu.

## Praktik yang dijaga

- Periode uji (Feb–Mei 2022) dipisah utuh, model tidak pernah melihat cuacanya.
- Validasi `GroupKFold` per tanggal. KFold acak bocor karena jam-jam dalam sehari hampir kembar.
- Batas alarm dikalibrasi dari prediksi out-of-fold, bukan dari data uji.
- Aturan penyebab disusun dengan suntikan pada data latih (`python -m ml.evaluate --tune`).
- Kejadian dihitung terdeteksi hanya bila alarmnya tidak muncul pada salinan tanpa gangguan.

## Berubah dari rencana awal

| Rencana | Sekarang | Alasan |
|---|---|---|
| Alarm setelah 2 jam berturut-turut | CUSUM | Cuaca satelit terlalu berisik: aturan 2 jam hanya menangkap kabel putus (panel kotor 7%) |
| Satu batas alarm | Derau dihitung per kondisi langit | Saat cerah cuaca jauh lebih bisa dipercaya daripada saat berawan |
| Kaggle | La Réunion | Lisensi terbuka, tropis, ada gangguan nyata |
| Baterai simulasi | Rekaman nyata BBOXX | Spesifikasi hampir sama: panel 50 Wp, aki 12 V |
| — | Tambahan: pembanding unit tetangga | Temuan terkuat. Lihat `docs/evaluasi.md` |
