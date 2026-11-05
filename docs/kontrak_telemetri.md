# Kontrak telemetri: alat IoT → model

Ini yang harus dikirim alat supaya bisa dinilai model. Pasangannya, kontrak keluaran ke dashboard, ada di `README.md`.

## Alur

```
Alat (ESP32 + sensor)  →  server tim  →  telemetri.csv  →  python -m ml.score  →  output/hasil_deteksi.csv  →  dashboard + bot
```

Cara kirim (HTTP/MQTT) bebas. Model hanya butuh tabel dengan kolom di bawah. Server cukup menyimpan **8+ hari terakhir**
lalu menjalankan `ml.score` tiap jam. Model tidak menyimpan status, jadi kalau server mati tidak ada yang hilang.

## Kolom per pembacaan

| Kolom | Tipe | Satuan | Wajib | Arti |
|---|---|---|---|---|
| `timestamp` | ISO 8601 **dengan zona waktu** | — | ya | Waktu baca, mis. `2026-11-05T10:20:00+08:00`. Alat perlu jam dari NTP/RTC |
| `unit_id` | teks | — | ya | Nama unit, mis. `PJU-01` |
| `pv_v` | angka | V | ya | Tegangan panel, **sisi panel sebelum controller** |
| `pv_i` | angka | A | ya | Arus panel, **sisi panel sebelum controller** |
| `batt_v` | angka | V | tidak | Tegangan aki. Kosong saat baris lain ada = model menganggap baterai dicabut |
| `batt_i_a` | angka | A | tidak | Arus aki. **Positif = mengisi**, sama seperti kontrak keluaran |

Kalau alat memang tidak memantau baterai, jangan kirim kolom `batt_v` sama sekali.

## Aturan

- **Interval baca:** bebas, minimal 3 pembacaan per jam. Saran: tiap 5–10 menit.
- **Baris rusak dibuang:** di luar 0–100 V, 0–30 A, aki 0–20 V, ±40 A. Duplikat `unit_id` + `timestamp` dibuang.
- **Kolom wajib hilang = gagal** dengan pesan jelas, karena itu salah kontrak, bukan data kotor.

## Contoh

```json
{"timestamp": "2026-11-05T10:20:00+08:00", "unit_id": "PJU-01", "pv_v": 18.2, "pv_i": 2.1, "batt_v": 13.4, "batt_i_a": 1.8}
```

## Yang perlu dikonfirmasi Yoga

1. **Posisi sensor:** model butuh produksi panel, jadi `pv_v` dan `pv_i` harus di antara panel dan controller.
2. **Aki penuh:** saat aki penuh controller mengerem panel, produksi turun padahal panel sehat. Model mengabaikan jam dengan
   `batt_v ≥ 14,4 V` (`battery.full_v` di `ml/config.yaml`). Angka ini harus disesuaikan dengan controller dan jenis aki.
3. **Lokasi dan panel final:** isi di `ml/situs_contoh.yaml`.

## Lokasi baru

Unit baru langsung jalan dengan **pvlib saja**. Koreksi XGBoost khas lokasi, jadi model La Réunion tidak dipakai di Indonesia.
Setelah 2–4 minggu data normal, latih ulang di lokasi itu dengan data telemetri (`ml/residual.py`, `ml/train.py`).
