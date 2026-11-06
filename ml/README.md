# ML: alarm sadar-cuaca

Menilai apakah produksi panel menyimpang karena gangguan, bukan karena cuaca, lalu menebak penyebab dan rugi rupiahnya.
Hasil lengkap: `docs/hasil_evaluasi.md`. Rancangan dan keterbatasan: `docs/evaluasi.md`.

## Menjalankan (dari root repo)

```bash
pip install -r requirements.txt       # macOS: brew install libomp
python -m pytest ml/tests             # test, tanpa internet
python -m ml evaluate                 # hasil, grafik, output/hasil_deteksi.csv
python -m ml train                    # latih ulang model La Réunion
python -m ml prepare                  # unduh ulang data mentah, ±30 menit
python -m ml evaluate --tune          # uji aturan penyebab di data latih
```

## Alur

```
data/        semua sumber -> satu tabel per jam
features.py  cuaca + fisika pvlib
model.py     XGBoost, kalibrasi, simpan-muat model per lokasi
detection/   kekurangan -> CUSUM -> alarm -> penyebab -> rupiah -> baris kontrak v1
evaluation/  suntikan gangguan, metrik, grafik, file demo
service.py   score() dan train() untuk kode lain
```

| File | Tugas |
|---|---|
| `data/sources.py` | Pembaca tiap sumber: La Réunion, BBOXX, telemetri alat |
| `data/weather.py` | Open-Meteo: historis dan terbaru |
| `data/prepare.py` | Unduh, simpan, dan muat `data/processed/` |
| `features.py` | Estimasi pvlib, penggabungan tabel, acuan tetangga dan sensor |
| `model.py` | Tuning, out-of-fold, kalibrasi, artifact per lokasi |
| `detection/detector.py` | Derau, CUSUM, threshold pembanding |
| `detection/causes.py`, `battery.py`, `rupiah.py` | Aturan penyebab, baterai, rugi |
| `detection/pipeline.py` | **Satu jalur skor** untuk data historis dan IoT |
| `evaluation/` | `faults`, `experiments`, `report`, `demo`, `run` |
| `config.yaml` | Parameter umum |
| `sites/<lokasi>.yaml` | Lokasi, panel, tarif |
| `artifacts/<lokasi>/` | Model dan kalibrasi lokasi itu |

**Sumber data baru:** tambah satu fungsi di `data/sources.py` yang menghasilkan tabel per jam dengan kolom `p_actual`.

**Lokasi baru:** tambah `sites/<lokasi>.yaml`. Sebelum dilatih, lokasi itu memakai pvlib dengan profil derau bawaan.

## Dipakai sebagai service

`ml.service` menerima dan mengembalikan tabel, tanpa membaca atau menulis file:

```python
from ml.service import score, train

hasil = score(readings, site="contoh")   # tabel kontrak v1
train(readings_normal, site="contoh")    # setelah 2-4 minggu data normal satu unit
```

Skor tidak menyimpan status, jadi cukup kirim riwayat 8+ hari. Input salah memunculkan `ValueError`. Kontrak alat ada di `docs/kontrak_telemetri.md`. Untuk FastAPI, satu endpoint cukup memanggil `score()`:

```python
@app.post("/score")
def score_endpoint(body: ScoreRequest):
    return score(pd.DataFrame(body.readings), site=body.site).to_dict("records")
```

Dari terminal:

```bash
python -m ml score --telemetry telemetri.csv --site contoh
python -m ml fit-site --telemetry normal.csv --site contoh
```

## Praktik yang dijaga

- Periode uji (Feb–Mei 2022) dipisah utuh, model tidak pernah melihat cuacanya.
- Validasi `GroupKFold` per tanggal. KFold acak bocor karena jam-jam dalam sehari hampir kembar.
- Batas alarm dikalibrasi dari prediksi out-of-fold, bukan dari data uji.
- Aturan penyebab disusun dengan suntikan pada data latih (`python -m ml evaluate --tune`).
- Kejadian dihitung terdeteksi hanya bila alarmnya tidak muncul pada salinan tanpa gangguan.

## Berubah dari rencana awal

| Rencana | Sekarang | Alasan |
|---|---|---|
| Alarm setelah 2 jam berturut-turut | CUSUM | Cuaca satelit terlalu berisik: aturan 2 jam hanya menangkap kabel putus (panel kotor 7%) |
| Satu batas alarm | Derau dihitung per kondisi langit | Saat cerah cuaca jauh lebih bisa dipercaya daripada saat berawan |
| Kaggle | La Réunion | Lisensi terbuka, tropis, ada gangguan nyata |
| Baterai simulasi | Rekaman nyata BBOXX | Spesifikasi hampir sama: panel 50 Wp, aki 12 V |
| — | Tambahan: pembanding unit tetangga | Temuan terkuat. Lihat `docs/evaluasi.md` |
