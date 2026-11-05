# Draf proposal

## Metode AI dan Hasil Evaluasi

**Masalah alarm biasa.** Alarm yang memakai batas daya tetap tidak bisa membedakan panel rusak dari langit mendung. Akibatnya alarm sering berbunyi palsu saat mendung, sedangkan panel kotor yang kehilangan 20% produksi tidak pernah terdeteksi.

**Estimasi produksi seharusnya.** Sistem menghitung daya yang seharusnya dihasilkan panel sehat pada cuaca saat itu. Rumus fisika (pvlib) memberi estimasi dasar, lalu XGBoost mengoreksi kesalahan khas lokasi. Masukannya data cuaca satelit gratis, karena alat murah di lapangan tidak memiliki sensor radiasi.

**Deteksi.** Selisih produksi dinilai relatif terhadap ketidakpastian cuaca saat itu, karena cuaca satelit jauh lebih andal saat cerah daripada saat berawan. Bukti dikumpulkan dengan CUSUM: satu jam menyimpang tidak memicu alarm, sedangkan gangguan kecil yang menetap terkumpul dalam beberapa hari. Daya nol saat seharusnya menghasilkan memicu alarm seketika. Penyebab ditebak dengan aturan yang dapat dijelaskan.

**Data dan pengujian.** Model dilatih pada data nyata PLTS atap beriklim tropis di La Réunion (Graillet dkk., 2023), lalu diuji pada empat bulan yang tidak pernah dilihat model. Validasi dibagi per tanggal agar tidak bocor. Pengujian memakai 90 kejadian gangguan yang **disuntikkan** dan 23 hari gangguan bayangan **nyata**. Data dari luar Indonesia dipakai karena belum ada data publik produksi panel di Indonesia.

**Hasil.**

| Pada alarm palsu yang setara | Alarm tetap | Sadar-cuaca (usulan) |
|---|---|---|
| Alarm palsu per minggu saat mendung | 1,53 | **0,44** |
| Panel kotor terdeteksi | 3% | **93%** |
| Bayangan terdeteksi (suntikan) | 15% | **55%** |
| Bayangan nyata terdeteksi | 9% | **39%** |
| Kabel putus terdeteksi | 100% | 95% |

Alarm palsu saat mendung turun 71%. XGBoost menurunkan galat estimasi 23% dibanding pvlib saja. Alarm tetap masih unggul untuk kabel putus dan alarm palsu saat cerah (0,09 vs 0,35 per minggu), karena gangguan yang membuat daya nol memang mudah dideteksi.

**Temuan tambahan.** Membandingkan satu unit dengan unit tetangganya menaikkan deteksi bayangan nyata menjadi 96% tanpa alarm palsu saat mendung. Pendekatan ini cocok untuk deretan PJU, tetapi butuh minimal dua unit berdekatan.

**Rugi rupiah.** Rugi dihitung dari energi hilang dikali tarif P-3/TR Rp1.699,53/kWh (asumsi, untuk PJU). Komponen baterai dan patroli: [menunggu `docs/rupiah.md`].

**Keterbatasan.** Data bukan dari Indonesia. Selain bayangan, semua gangguan disuntikkan. Data 1,8 kW diskalakan ke panel 50 Wp. Tebakan penyebab baru andal untuk kabel putus (100%); pola lain 36–45%, sehingga ditampilkan sebagai petunjuk awal. Rekaman baterai berasal dari sistem di Afrika dan aturan baterai melemah baru menandai 10 dari 25 baterai yang masuk perbaikan.
