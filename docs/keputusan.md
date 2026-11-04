# Keputusan tim (Yoga)

Status: **draf**. Bagian bertanda TODO belum diputuskan; setelah diputuskan, salin ke `config.yaml`.

## Scope v2

- Pemantau untuk instalasi panel surya + baterai **yang sudah terpasang** (PJU surya, PLTS sekolah/puskesmas, UMKM).
- Untuk pendaftaran: dibuktikan dengan **simulasi dan data publik**. Alat fisik = rancangan (skema rangkaian + BOM), tanpa pembelian komponen.
- Keluaran: alarm sadar-cuaca, tebakan penyebab, rugi Rp, notifikasi Telegram, dashboard.
- Di luar scope: pemasangan lapangan, model baterai lengkap (SoH), aplikasi mobile.

## Lokasi data cuaca

- TODO(Yoga): lokasi final. Sementara di `config.yaml`: **CONTOH Badung, Bali** (-8.65, 115.18), zona `Asia/Makassar` (WITA, +08:00).
- Alasan pemilihan: TODO (mis. kasus PJU Badung 218 titik, lihat `docs/sumber.md` Rafie).

## Spesifikasi panel acuan

| Parameter | Nilai | Sumber/asumsi |
|---|---|---|
| Daya puncak | 50 Wp | ketetapan tim |
| Koefisien suhu daya | -0,4 %/°C | tipikal silikon (asumsi) |
| Kemiringan / arah | 10° / menghadap utara | asumsi, TODO cek |
| Rugi sistem | 14 % | asumsi |
| Sistem | 12 V, baterai TODO Ah, controller TODO | TODO(Yoga+Bobi), lihat `docs/bom.md` |

## Kontrak data

v1 disepakati 4 Nov 2026, lihat `README.md` → "Kontrak data v1".

## Log keputusan

| Tanggal | Keputusan | Oleh |
|---|---|---|
| 4 Nov 2026 | Format keluaran model = usulan Christian + `batt_i_a`, `alarm_threshold`, `data_source`, `fault_label`; zona waktu lokasi | Yoga, Christian |
