# Evaluasi: alarm biasa vs alarm sadar-cuaca

Angka lengkap dibuat otomatis di `docs/hasil_evaluasi.md`.

**Pertanyaan:** apakah membandingkan produksi aktual dengan produksi seharusnya memberi lebih sedikit alarm palsu saat mendung,
tanpa kehilangan deteksi gangguan?

## Rancangan

- **Data:** produksi nyata La Réunion (tropis, 2 inverter, Okt 2021–Apr 2023), radiasi satelit SARAH3, suhu dan angin ERA5.
- **Latih:** inverter 2 (tanpa gangguan) di luar periode uji. 3.412 jam siang. XGBoost dituning dengan `GroupKFold` per tanggal.
- **Uji:** Feb–Mei 2022, dipisah utuh karena semua gangguan nyata ada di sini.
- **Kalibrasi:** batas alarm dicari dari prediksi out-of-fold dengan target 0,5 alarm palsu per minggu.
- **Uji A (suntikan):** 4 pola, 9 variasi, 10 kejadian per variasi, disuntikkan ke salinan data uji inverter 2.
- **Uji B (nyata):** 23 hari bayangan berlabel di inverter 1. Pembandingnya inverter 2 pada jam yang sama.
- **Metrik:** alarm palsu per minggu (cerah dan mendung), recall per kejadian, delay, ketepatan penyebab.

## Hasil utama

| | Threshold (alarm palsu disamakan) | pvlib + CUSUM | **pvlib + XGBoost + CUSUM** | Unit tetangga + CUSUM |
|---|---|---|---|---|
| Alarm palsu/minggu saat mendung | 1,53 | 0,22 | **0,44** | 0,00 |
| Alarm palsu/minggu saat cerah | 0,09 | 0,26 | **0,35** | 0,35 |
| Recall kabel putus | 1,00 | 0,95 | **0,95** | 0,90 |
| Recall panel kotor | 0,03 | 0,77 | **0,93** | 1,00 |
| Recall bayangan (suntikan) | 0,15 | 0,35 | **0,55** | 1,00 |
| Recall konektor kendor | 0,40 | 0,35 | **0,50** | 0,70 |
| Recall bayangan **nyata** | 0,09 | 0,43 | **0,39** | 0,96 |

MAE produksi seharusnya di data uji: pvlib 0,089, pvlib + XGBoost 0,069 (turun 23%).

## Cara membacanya

1. **Sadar-cuaca menang di tujuan utamanya.** Alarm palsu saat mendung turun dari 1,53 menjadi 0,44 per minggu, dan panel kotor yang hampir tidak pernah tertangkap threshold (3%) kini 93%.
2. **Threshold lebih unggul di dua hal.** Kabel putus 100% vs 95%, dan alarm palsu saat cerah lebih sedikit (0,09 vs 0,35). Gangguan yang membuat daya nol memang mudah bagi threshold.
3. **XGBoost membantu, tapi tidak di semua hal.** Error turun 23% dan recall gangguan kecil naik. Namun alarm palsu lebih banyak (0,38 vs 0,25 per minggu total) dan bayangan nyata sedikit lebih rendah (0,39 vs 0,43).
4. **Gangguan kecil lambat.** Panel kotor baru terdeteksi setelah sekitar 4–9 hari (median per variasi). Kabel putus terdeteksi dalam jam yang sama.
5. **Temuan terkuat: unit tetangga.** Dua inverter di satu atap berselisih hanya sekitar 2–5% pada kondisi normal, jauh lebih rapat dari cuaca satelit. Membandingkan PJU dengan tetangganya hampir menyamai sensor mahal di lokasi. Syaratnya ada ≥2 unit berdekatan, dan gangguan yang menimpa semua unit bersamaan tidak terlihat.

## Tebakan penyebab

Hanya **kabel putus yang andal (100%)**. Panel kotor 36%, bayangan 45%, konektor kendor 40%. Pada acuan tetangga lebih rendah lagi (0–21%), karena alarm menyala saat kekurangannya masih kecil dan aturannya dibuat untuk cuaca. Jadi `cause_guess` selain kabel putus harus dibaca sebagai petunjuk awal, bukan diagnosis.

## Baterai

Aturan penurunan tegangan per Ah pada 27 baterai nyata BBOXX menandai 10 dari 25 baterai yang akhirnya masuk perbaikan. Hanya 2 baterai sehat ada di sampel, jadi tingkat alarm palsunya **belum bisa disimpulkan**. Catatan perbaikan BBOXX juga tidak menyebut penyebabnya, jadi tidak semua berarti baterai lemah.

## Keterbatasan (wajib ditulis di proposal)

- Data dari La Réunion, bukan Indonesia. Cuaca uji memakai SARAH3, sedangkan di Indonesia nanti Himawari.
- Selain bayangan, semua gangguan disuntikkan. Parameter suntikan masih default karena `docs/pola_gangguan.md` belum ada.
- Data 1,8 kW diskalakan ke 50 Wp. Panel tunggal lebih peka terhadap bayangan sebagian.
- Data per jam hanya ada saat inverter hidup, jadi jam malam tidak terlihat di data panel.
- Perilaku controller saat aki penuh tidak teruji, karena PLTS ini tersambung ke jaringan.
- Hanya 23 hari gangguan nyata, dan hari-hari itu berdekatan, jadi skor alarm bisa terbawa antarhari.
- Data uji dijalankan lebih dari sekali saat perbaikan bug dan pembatasan skor. Tidak ada ambang yang dituning dari hasil uji.
- Komponen patroli dan baterai pada `loss_rp` masih Rp0 sampai `docs/rupiah.md` ada, jadi rupiah saat ini hanya energi hilang.
