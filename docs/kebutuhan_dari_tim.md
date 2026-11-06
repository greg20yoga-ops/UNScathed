# Yang Dibutuhkan dari Tim

Dari: Christian · Kamis, 5 November 2026
Konteks lengkap: `docs/update_ml_untuk_tim.md`

Proposal dikirim **Jumat, 6 November sebelum 21.00**. Supaya angkanya sempat dihitung ulang dan diaudit, usahakan semua input masuk paling lambat **Jumat 10.00**.

Kalau ada yang belum sempat, kabari saja di grup. Semua sudah punya nilai sementara, jadi tidak ada yang berhenti total. Bedanya, nilai sementara harus ditulis sebagai asumsi di proposal.

## Ringkasan

| Siapa | Yang dibutuhkan | Paling lambat | Kalau belum ada |
|---|---|---|---|
| Yoga | Masukkan draf metode ke proposal | **Hari ini, sebelum 12.00** | Bagian AI kosong di draf ke dosen |
| Yoga | Setujui perubahan kontrak + merge | Kamis malam | Dashboard tim tetap memakai data lama |
| Yoga | Posisi sensor | Jumat 10.00 | Rancangan alat dan kontrak telemetri bisa tidak cocok |
| Yoga | Jenis controller + aki | Jumat 10.00 | Batas aki penuh tetap asumsi 14,4 V |
| Yoga | Lokasi + spesifikasi panel final | Jumat 10.00 | Tetap contoh Badung |
| Bobi | `docs/pola_gangguan.md` | Jumat 10.00 | Pengujian memakai parameter buatan Christian |
| Bobi | `docs/tabel_uji.md` | Hari ini 23.59 | Datanya sudah tersedia |
| Bobi | Pertanyaan tambahan narasumber | Saat wawancara | Klaim kebutuhan pengguna lebih lemah |
| Rafie | `docs/rupiah.md` | Jumat 10.00 | `loss_rp` hanya energi hilang |
| Rafie | Konfirmasi tarif resmi PLN | Jumat 10.00 | Sumber tetap berita |
| Rafie | Audit angka AI + biaya data | Jumat 12.00 | Biaya operasional bisa terlalu rendah |

---

## Yoga

### 1. Masukkan draf metode ke proposal (hari ini, sebelum 12.00)

Ambil dari `docs/proposal_draf.md` di branch `christian-ml`. Bagian rupiah masih bertanda "menunggu" sampai `docs/rupiah.md` ada.

### 2. Setujui perubahan kontrak, lalu merge (Kamis malam)

Daftarnya ada di bagian 6 `docs/update_ml_untuk_tim.md`. Yang paling perlu dicek: `site` di `config.yaml` jadi La Réunion supaya jam dashboard benar.

### 3. Posisi sensor (Jumat 10.00)

**Pertanyaan:** sensor arus dan tegangan di rancangan alat 12 V dipasang di mana?

- Antara panel dan controller
- Antara controller dan aki
- Dua-duanya

**Kenapa penting:** model butuh produksi panel, jadi harus ada sensor di antara panel dan controller. Baterai butuh sensor tersendiri kalau mau memantau `batt_v` dan `batt_i_a`.

**Yang dipakai sementara:** sensor panel ada di antara panel dan controller. PJU diasumsikan tanpa inverter, jadi yang dipakai daya DC.

### 4. Controller dan aki (Jumat 10.00)

**Pertanyaan:**

- Controllernya PWM atau MPPT?
- Saat aki penuh, tegangan berapa dan apakah controller punya status yang bisa dibaca?
- Aki jenis apa (aki basah, VRLA, LiFePO4) dan berapa Ah?

**Kenapa penting:** saat aki penuh, controller mengerem panel. Produksi turun padahal panel sehat. Kalau tidak ditangani, alarm palsu bisa muncul pada siang yang cerah. Dataset kita tidak punya kondisi ini, karena PLTS-nya tersambung ke jaringan.

**Yang dipakai sementara:** jam dengan `batt_v ≥ 14,4 V` diabaikan. Aturan baterai melemah dikalibrasi untuk aki 20 Ah, jadi kapasitas lain perlu disesuaikan.

### 5. Lokasi dan spesifikasi panel final (Jumat 10.00)

Isi `ml/sites/contoh.yaml`: lintang, bujur, ketinggian, zona waktu, kemiringan, dan arah panel. Sekarang masih contoh Badung.

Ini hanya untuk jalur alat di lapangan. Hasil evaluasi tetap dari La Réunion.

### 6. Demo

- Pakai `output/hasil_deteksi.csv` yang baru.
- Skenario "panel tertutup" perlu perhatian: alarmnya bunyi, tapi `PJU-demo-bayangan` salah tebak jadi konektor kendor. Pilihannya, tampilkan apa adanya sebagai "petunjuk awal", atau ganti ke `PJU-demo-panel-kotor`.
- Kalau demo v1 sudah direkam dari data lama, perlu rekam ulang supaya angkanya sama dengan proposal.

### 7. Untuk tahap hackathon

Server cukup menyimpan riwayat 8+ hari dan memanggil `ml.service.score()` tiap jam. Kontraknya ada di `docs/kontrak_telemetri.md`. Ini tidak diperlukan untuk pendaftaran.

---

## Bobi

### 1. Tabel pola gangguan: `docs/pola_gangguan.md` (Jumat 10.00)

Dokumen ini belum ada di repo. Pengujian saat ini memakai angka buatan Christian, jadi perlu divalidasi atau diganti. Format yang dibutuhkan:

| Pola | Tanda di data | Besar | Durasi | Alarm yang diharapkan | Penyebab | Sumber |
|---|---|---|---|---|---|---|

Angka yang dipakai sekarang:

| Pola | Besar | Durasi |
|---|---|---|
| Kabel putus | Daya jadi nol | 1 dan 3 hari |
| Panel kotor | Turun 1, 2, dan 4% per hari, maksimal 30%, pulih setelah hujan > 5 mm per hari | 21, 14, dan 10 hari |
| Bayangan | Turun 30% dan 60%, 2 jam per hari di jam yang sama | 5 hari |
| Konektor kendor | Tiap jam peluang 30% turun acak ke 30–100% | 2 dan 5 hari |

**Yang paling membantu:** seberapa cepat panel di Indonesia kotor dan berapa lama bayangan biasanya bertahan, lengkap dengan sumbernya.

### 2. Tabel uji: `docs/tabel_uji.md` (hari ini, 23.59)

Datanya sudah ada di bagian "Hasil per skenario" pada `docs/hasil_evaluasi.md`. Kolom `usulan` adalah sistem utama. Hitungan per kejadian ada di `bukti/hasil_evaluasi.csv`.

Tulis keduanya: apakah alarm keluar, dan apakah penyebabnya benar. Dua angka itu berbeda jauh, jadi jangan digabung.

Kolom `variant` mengikuti urutan variasi di tabel atas, dan `method` berisi `usulan` atau `tetangga`.

Hasil baterai tulis di tabel terpisah. "Baterai dicabut" adalah uji fungsi pada data suntikan, sedangkan "baterai melemah" memakai data nyata dengan hasil 10 dari 25.

### 3. Pertanyaan tambahan untuk narasumber

Jawaban ini langsung menentukan apakah klaim kita relevan:

1. Berapa kali alarm palsu per minggu yang masih bisa diterima?
2. Kerusakan biasanya ketahuan setelah berapa lama? Apakah telat 4–9 hari untuk panel kotor masih berguna?
3. Berapa jarak antar tiang PJU surya, dan apakah satu ruas biasanya memakai panel yang sama? Ini untuk fitur pembanding tetangga.
4. Seberapa sering patroli, dan berapa biayanya? Jawaban ini juga dibutuhkan Rafie.
5. Bagaimana siang hari saat aki penuh: apakah controllernya bisa dibaca datanya?

### 4. Keselamatan

Saat mengaudit `docs/keselamatan.md`, cek bahwa sensor di sisi panel sudah masuk rancangan sekring dan kabel. Posisinya menunggu jawaban Yoga.

---

## Rafie

### 1. Rumus rupiah: `docs/rupiah.md` (Jumat 10.00)

Dokumen ini belum ada di repo. Yang saya butuhkan:

| Nilai | Satuan | Cara dipakai di kode | Sekarang |
|---|---|---|---|
| Tarif | Rp/kWh | Energi hilang × tarif, per jam | Rp1.699,53 (P-3/TR) |
| Biaya patroli | Rp per kejadian | Ditambah sekali saat alarm menyala, untuk gangguan yang butuh teknisi | Rp0 |
| Biaya baterai | Rp per kejadian | Ditambah sekali untuk baterai dicabut atau melemah | Rp0 |

Beri sumber dan label asumsi untuk tiap angka. Biaya baterai perlu dibuat per kejadian, misalnya harga aki dibagi umur pakai, supaya tidak dihitung berlebihan.

Kalau rumusnya tidak cocok dengan bentuk di atas, kabari dan akan saya sesuaikan.

### 2. Rugi energi ternyata kecil

Panel 50 Wp hanya menghasilkan sekitar 0,2 kWh per hari, atau sekitar Rp340. Di file demo, kabel putus 2 hari cuma rugi sekitar Rp1.000.

Jadi nilai jual tidak bisa bertumpu pada energi hilang. Argumen bisnisnya perlu ke lampu PJU yang mati, baterai cepat rusak, dan biaya patroli. Untuk itu angka patroli dan baterai dari kamu penting.

### 3. Tarif resmi (Jumat 10.00)

Tarif yang dipakai sekarang bersumber dari berita. Tolong carikan halaman tarif resmi PLN untuk P-3/TR dan B-2/TR, dan konfirmasi golongan yang dipakai.

### 4. Biaya data untuk versi komersial

Ini perlu masuk hitungan hilirisasi:

- **Open-Meteo gratis hanya untuk non-komersial.** Kalau produk dijual, perlu paket berbayar atau sumber lain. Harganya belum saya cek.
- **Data baterai BBOXX** CC BY-NC, jadi hanya aman untuk riset dan lomba.
- **Solcast** bisa jadi opsi upgrade cuaca, harganya perlu minta penawaran.

### 5. Sudut bisnis dari temuan baru

Pembanding unit tetangga bisa jadi nilai jual untuk Dishub atau pemda: makin banyak PJU dalam satu ruas yang dipantau, makin akurat deteksinya. Ini baru diuji pada dua inverter di satu atap, jadi tulis sebagai potensi.

### 6. Audit angka AI (Jumat 12.00)

Cocokkan angka di `docs/proposal_draf.md` dengan `docs/hasil_evaluasi.md`:

- Alarm palsu saat mendung 1,53 → 0,44 per minggu (turun 71%)
- Panel kotor 3% → 93%
- Bayangan suntikan 15% → 55%
- Bayangan nyata 9% → 39%
- Kabel putus 100% → 95%
- Error tebakan produksi turun 23%

---

## Dari Christian

| Setelah terima | Yang saya kerjakan |
|---|---|
| Tabel pola Bobi | Update parameter, jalankan ulang evaluasi, update semua angka |
| Rumus Rafie | Update `loss_rp`, buat ulang file dashboard |
| Jawaban Yoga soal sensor dan controller | Sesuaikan kontrak telemetri dan batas aki penuh |

**Penting:** kalau tabel Bobi mengubah parameter, angka di proposal ikut berubah. Karena itu, draf ke dosen hari ini mungkin bukan angka final, dan audit Rafie sebaiknya dilakukan setelah evaluasi terakhir dijalankan.
