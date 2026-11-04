# Rancangan evaluasi (alarm biasa vs alarm sadar-cuaca)

**Pertanyaan:** apakah membandingkan produksi aktual dengan produksi yang seharusnya (dari cuaca) memberi
lebih sedikit alarm palsu saat mendung, tanpa kehilangan deteksi gangguan nyata?

**Tiga metode, data sama:**
1. `threshold`: alarm bila daya < 30% pdc0 pada jam 09-15 (alarm biasa)
2. `pvlib`: alarm bila aktual/seharusnya (model fisik pvlib) < ambang
3. `pvlib_ml`: sama, tetapi seharusnya dikoreksi model ML ringan (GradientBoosting) yang dilatih pada data SEHAT

**Metrik:** alarm palsu per minggu (data tanpa gangguan), alarm palsu pada hari mendung, recall per pola,
delay deteksi (jam), akurasi tebakan penyebab.

**Anti-kebocoran:** pembagian latih/uji berdasarkan WAKTU; gangguan hanya disuntik ke bagian uji;
ML hanya melihat data latih sehat. Akurasi mendekati 100% = curiga bocor.

**Keterbatasan (tulis di proposal):** gangguan disuntikkan, bukan kejadian lapangan; data publik dari lokasi
di luar Indonesia; panel disetarakan ke 50 Wp lewat normalisasi skala.

Hasil terbaru: lihat `docs/hasil_evaluasi.md` (otomatis) dan `bukti/`.
