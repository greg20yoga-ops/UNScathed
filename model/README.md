# Model alarm sadar-cuaca (bagian Christian) - jalankan semua perintah dari ROOT repo

UNS Innovation Hackathon 2026, subtema A, ide v2.
Alarm hanya berbunyi bila ada kerusakan, **bukan** karena mendung: aktual dibandingkan dengan produksi yang
seharusnya dari cuaca (pvlib + koreksi ML ringan), lalu tebak penyebab dan hitung rugi Rp.

> **Peringatan:** angka dari `--source synthetic` hanya untuk menguji pipeline. Jangan dikutip sebagai hasil di proposal.

## Jalankan (5 menit)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m model.run --source synthetic                  # demo tanpa internet (SINTETIS)
```

Keluaran: `data/sim/output_<skenario>.csv` (dibaca dashboard Yoga), `bukti/grafik_perbandingan.png`,
`bukti/grafik_metrik.png`, `bukti/hasil_evaluasi.csv`, `docs/hasil_evaluasi.md`.

## Tiga sumber data

| Perintah | Cuaca | Produksi aktual | Status |
|---|---|---|---|
| `--source synthetic` | buatan | buatan | teruji |
| `--source openmeteo` (jalankan `python scripts/fetch_weather.py` dulu) | NYATA | buatan | jalur kode teruji dengan CSV palsu; panggilan API belum diuji |
| `--source kaggle` (taruh 2 CSV Plant_1 di `data/raw/kaggle/`) | NYATA | NYATA | teruji dengan CSV palsu berskema sama; **belum dicoba pada file asli**, cek kolom bila error |

Data nyata tidak punya label gangguan, jadi gangguan **disuntikkan** (`model/fault_injection.py`, parameter di `config.yaml`).
Pembagian latih/uji berdasarkan waktu. Kolom `data_source` di tiap CSV keluaran dan judul grafik memuat label sumber data.

## Peta ke tugas Christian

| Tugas | File |
|---|---|
| Data cuaca + sumber | `scripts/fetch_weather.py`, `docs/sumber_data.md` |
| Produksi seharusnya (pvlib) | `model/expected_pv.py` |
| Rancangan evaluasi | `docs/evaluasi.md` |
| Generator gangguan | `model/fault_injection.py` + `faults:` di `config.yaml` |
| Dua detektor (+ ML) | `model/detectors.py`, `model/ml_residual.py` |
| Tebakan penyebab (aturan) | `model/cause.py` |
| Kolom `alarm, cause_guess, loss_rp` | `model/evaluate.py`, `model/contract.py` |
| Grafik perbandingan | `bukti/grafik_perbandingan.png` |

## Yang HARUS disamakan dengan tim (belum saya ketahui)

- [ ] **Kontrak data v1** (README repo tim): samakan nama kolom di `model/contract.py`.
- [ ] **Lokasi + spesifikasi panel 50 Wp** (Yoga, `docs/keputusan.md`): ganti `site:` dan `panel:` di `config.yaml` (sekarang contoh Badung).
- [ ] **Rumus rugi Rp** (Rafie, `docs/rupiah.md`): sekarang hanya energi hilang x Rp1.445/kWh (`_loss_rp` di `evaluate.py`).
- [ ] **Tabel pola gangguan** (Bobi, `docs/pola_gangguan.md`): terjemahkan ke `faults:` di `config.yaml`.
- [ ] Pola **baterai** (baterai dicabut, baterai melemah) belum tercakup: model ini hanya sisi produksi PV.

## Batasan yang sudah diketahui

- Derating ringan (batas daya 55% pdc0) tidak terdeteksi oleh aturan median 6 jam; derating berat terdeteksi tetapi tebakan penyebabnya belum andal.
- Pada data sintetis, `pvlib_ml` tidak lebih baik dari `pvlib` (bias data buatan kecil). Bila itu juga terjadi di data nyata, laporkan apa adanya.
- Tebakan penyebab berbasis aturan, jadi bukan ML.
- Soiling 1%/hari butuh sekitar 3 pekan untuk terdeteksi pada ambang 0,80; ini sifat ambang, bukan bug.

## Push ke repo tim (UNScathed)

```bash
git clone https://github.com/greg20yoga-ops/UNScathed.git && cd UNScathed
# salin isi paket ini ke root repo (README.md root milik tim tidak ditimpa)
git checkout -b christian-model
git add . && git commit -m "Tambah model alarm sadar-cuaca (pvlib + ML ringan), evaluasi, bukti"
git push -u origin christian-model     # lalu buka Pull Request ke main
```
Butuh akses tulis: minta Yoga menambahkan akun GitHub kamu sebagai collaborator (Settings > Collaborators),
atau fork repo lalu buka Pull Request dari fork.
