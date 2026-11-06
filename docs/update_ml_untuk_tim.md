# Update ML untuk Tim

Dari: Christian · Kamis, 5 November 2026
Kode: branch [`christian-ml`](https://github.com/greg20yoga-ops/UNScathed/tree/christian-ml), belum di-merge

## Ringkasan

Bagian ML sudah jalan dari data sampai dashboard, memakai data panel nyata, bukan data sintetis lagi.

Hasil utamanya: dibanding alarm biasa, alarm palsu saat mendung turun 71%, dan panel kotor yang tadinya hampir tidak pernah tertangkap (3%) sekarang tertangkap 93%. Kabel putus sedikit lebih rendah (95% vs 100%).

Yang masih lemah: tebakan penyebab baru andal untuk kabel putus.

Tiga hal yang perlu kalian tahu dulu:

1. **Draf "Metode AI dan Hasil Evaluasi" sudah ada** di `docs/proposal_draf.md`, siap disatukan.
2. **Ada perubahan kontrak data** yang perlu disetujui sebelum merge (lihat bagian 6).
3. **Masih ada input yang ditunggu** dari Yoga, Bobi, dan Rafie. Rinciannya di `docs/kebutuhan_dari_tim.md`.

## 1. Cara kerja sistem sekarang

```
Cuaca satelit (internet)  ──►  tebak produksi SEHARUSNYA (pvlib + XGBoost)
                                          │
Listrik panel (alat)      ──►  produksi AKTUAL
                                          │
                     bandingkan keduanya, kumpulkan bukti dari jam ke jam
                                          │
                     bukti cukup ──► ALARM ──► tebak penyebab ──► hitung rugi Rp
                                          │
                     output/hasil_deteksi.csv ──► dashboard + bot Telegram
```

Intinya: alarm bukan melihat "daya rendah", tapi "daya lebih rendah dari yang seharusnya untuk cuaca saat itu". Jadi mendung tidak otomatis dianggap gangguan.

## 2. Yang berubah dari rencana awal

| Rencana awal | Sekarang | Kenapa |
|---|---|---|
| Data panel dari Kaggle (India, 34 hari) | **La Réunion** (pulau tropis, ±1,5 tahun, 2 inverter) | Lisensi Kaggle tidak terbuka dan lokasinya tidak diketahui. La Réunion tropis, lisensinya CC BY 4.0, dan punya gangguan bayangan asli berlabel |
| Cuaca Open-Meteo biasa | **Cuaca satelit** dari Open-Meteo | Lebih mirip sensor asli (korelasi 0,86 vs 0,81). Tersedia untuk La Réunion dan Indonesia |
| Alarm setelah beberapa jam berturut-turut | **Skor bukti (CUSUM)** | Cuaca satelit bisa meleset jauh per jam. Dengan aturan 2 jam, panel kotor hanya tertangkap 7% |
| Data baterai simulasi | **Rekaman baterai nyata BBOXX** | Spesifikasinya hampir sama dengan PJU: panel 50 Wp, aki 12 V 20 Ah |
| Tidak ada | **Pembanding unit tetangga** | Temuan baru, lihat bagian 4 |

Yang tetap: satu model ML (XGBoost), penyebab pakai aturan, dan alat fisik berupa rancangan.

## 3. Hasil pengujian

Diuji pada Februari–Mei 2022, periode yang tidak pernah dilihat model saat latihan. Alarm biasa disetel supaya total alarm palsunya setara dengan usulan, jadi perbandingannya adil.

| | Alarm biasa | Usulan | Unit tetangga |
|---|---|---|---|
| Alarm palsu per minggu saat mendung | 1,53 | **0,44** | 0,00 |
| Alarm palsu per minggu saat cerah | 0,09 | **0,35** | 0,35 |
| Panel kotor tertangkap | 3% | **93%** | 100% |
| Bayangan tertangkap (suntikan) | 15% | **55%** | 100% |
| Bayangan **nyata** tertangkap | 9% | **39%** | 96% |
| Konektor kendor tertangkap | 40% | **50%** | 70% |
| Kabel putus tertangkap | 100% | **95%** | 90% |

"Suntikan" artinya gangguan dibuat buatan pada data nyata, 90 kejadian total. "Nyata" artinya 23 hari bayangan yang memang terjadi pada panel di dataset.

**Cara bacanya:**

- Usulan menang di tujuan utama: alarm palsu saat mendung dan gangguan yang tidak bikin daya nol.
- Alarm biasa masih unggul untuk kabel putus dan alarm palsu saat cerah.
- XGBoost menurunkan error tebakan produksi 23%. Tapi alarm palsu totalnya lebih banyak dibanding pvlib saja (0,38 vs 0,25 per minggu), dan bayangan nyata sedikit lebih rendah (39% vs 43%).
- Kabel putus langsung ketahuan. Panel kotor baru ketahuan setelah sekitar 4–9 hari.

## 4. Temuan baru: bandingkan dengan unit tetangga

Dua inverter di dataset dipasang di atap yang sama. Saat normal, produksinya hanya beda sekitar 2–5%. Itu jauh lebih rapat daripada cuaca satelit, jadi unit tetangga adalah acuan yang lebih akurat.

Bayangan nyata yang tertangkap naik dari 39% ke 96%, tanpa alarm palsu saat mendung pada periode uji.

Ini cocok untuk deretan PJU, misalnya kasus Badung 218 titik. Syaratnya minimal 2 unit berdekatan. Kekurangannya, gangguan yang menimpa semua unit sekaligus tidak terlihat, misalnya semua panel kotor bersamaan.

Yang diuji baru dua inverter di satu atap. Jarak antar tiang PJU yang lebih jauh belum diuji.

## 5. Yang boleh dan tidak boleh diklaim di proposal

**Boleh:**

- "Alarm palsu saat mendung turun 71% pada data uji."
- "Diuji pada data nyata PLTS tropis, dengan 90 gangguan suntikan dan 23 hari gangguan bayangan nyata."
- "Data batas alarm dan latihan dipisahkan dari data uji."

**Jangan:**

- Menyebut "akurasi X%" tanpa menyebut pola gangguannya.
- Menyebut sudah diuji di Indonesia atau di PJU sungguhan.
- Menyebut tebakan penyebab akurat. Yang andal hanya kabel putus (100%). Pola lain 36–45%.
- Menyebut bisa mendeteksi baterai melemah dengan andal. Aturan ini baru menandai 10 dari 25 baterai yang masuk perbaikan, dan baterai sehat di sampel cuma 2.
- Menyebut angka `loss_rp` sebagai rugi total. Saat ini isinya baru energi hilang.

## 6. Perubahan yang perlu disetujui sebelum merge

Kontrak data mewajibkan ini dikabarkan ke grup dulu.

| Perubahan | Dampak |
|---|---|
| `data_source` tambah `lareunion` dan `iot` | `dashboard/data.py` dan README sudah disesuaikan |
| `config.yaml` hanya berisi zona waktu dashboard (`Indian/Reunion`) | Supaya jam di dashboard benar. Lokasi pasang pindah ke `ml/sites/contoh.yaml` |
| Alarm memakai CUSUM | Tidak ada lagi `consecutive_h` |
| `model/`, `scripts/`, `data/sim/`, `bukti/grafik_metrik.png` dihapus | Digantikan `ml/`. Dashboard membaca `output/hasil_deteksi.csv` |
| `cause_guess` tidak pernah mengisi `inverter_derating` | Nilainya tetap ada di kontrak, tapi tidak dipakai |

Nama kolom, satuan, dan arah arus baterai **tidak berubah**. Kolom wajib tetap sama.

## 7. Isi repo yang bisa langsung dipakai

| File | Untuk | Isi |
|---|---|---|
| `output/hasil_deteksi.csv` | Yoga | 8 unit demo, 5–31 Maret 2022, sudah terbaca dashboard dan bot |
| `docs/proposal_draf.md` | Yoga | Bagian Metode AI dan Hasil Evaluasi |
| `docs/kontrak_telemetri.md` | Yoga, Bobi | Yang harus dikirim alat IoT |
| `docs/hasil_evaluasi.md` | Bobi | Hasil per skenario untuk `docs/tabel_uji.md` |
| `docs/evaluasi.md` | Semua | Rancangan, hasil, dan keterbatasan |
| `docs/sumber_data.md` | Rafie | Sumber dan lisensi semua data |
| `bukti/grafik_perbandingan.png` | Yoga | Grafik alarm biasa vs usulan |

## 8. Catatan untuk demo

Hasil di file demo tidak diedit, jadi ada yang salah tebak:

| Unit | Hasil | Catatan |
|---|---|---|
| `PJU-demo-kabel-putus` | Alarm, penyebab benar | Aman untuk demo |
| `PJU-demo-baterai-dicabut` | Alarm, penyebab benar | Aman untuk demo |
| `PJU-demo-baterai-melemah` | Alarm, penyebab benar | Rekaman baterai nyata yang masuk perbaikan |
| `PJU-demo-panel-kotor` | Alarm, penyebab benar | Aman untuk demo |
| `PJU-demo-bayangan` | Alarm, penyebab **salah** (konektor kendor) | Skenario "panel tertutup" di demo perlu perhatian |
| `PJU-demo-konektor-kendor` | Alarm, penyebab **salah** (panel kotor) | Sebaiknya tidak ditonjolkan |
| `PJU-demo-normal` | Satu alarm palsu, 29 Maret | Sesuai tingkat alarm palsu asli |

Rekaman baterai dan data panel berasal dari sistem berbeda, jadi keduanya tidak benar-benar sinkron. Data demo adalah data 2022 di La Réunion yang diskalakan ke panel 50 Wp, dan labelnya sudah ada di dashboard.

## 9. Keterbatasan yang wajib ditulis

- Data bukan dari Indonesia, dan uji memakai satelit SARAH3 sedangkan di Indonesia nanti Himawari.
- Selain bayangan, semua gangguan disuntikkan. Parameternya masih default.
- Data 1,8 kW per inverter diskalakan ke 50 Wp. Panel tunggal lebih peka terhadap bayangan sebagian.
- Perilaku controller saat aki penuh belum teruji, karena PLTS di dataset tersambung ke jaringan.
- Hanya 23 hari gangguan nyata, dan hari-harinya berdekatan.
- Komponen patroli dan baterai pada `loss_rp` masih Rp0.
- Data cuaca gratis dan data baterai hanya untuk non-komersial.

## 10. Cara menjalankan

```bash
git fetch origin && git checkout christian-ml
pip install -r requirements.txt       # macOS: brew install libomp
python -m pytest ml/tests             # 30 test
python -m ml evaluate                 # buat ulang hasil, grafik, dan file dashboard
streamlit run dashboard/app.py        # dashboard
```

Penjelasan teknis ada di `ml/README.md`.
