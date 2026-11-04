# Sumber data (isi tiap kali menambah data)

| Data | Sumber | Rentang | Lisensi / catatan | Label |
|---|---|---|---|---|
| Cuaca per jam | Open-Meteo Historical Weather API (`scripts/fetch_weather.py`) | (isi) | (cek ketentuan Open-Meteo) | NYATA |
| Produksi PV nyata | Kaggle "Solar Power Generation Data" (Plant_1) | 15 Mei - 17 Jun 2020 (cek) | (cek lisensi di halaman dataset) | NYATA, skala dinormalkan |
| Produksi PV nyata (opsional) | NREL PVDAQ | (isi) | (cek) | NYATA |
| Produksi aktual demo | `model/data_sources.simulate_actual` | - | buatan | SINTETIS |
| Gangguan | `model/fault_injection.py` | - | buatan, parameter di `config.yaml` | SUNTIKAN |

Aturan: setiap angka/grafik di proposal harus bisa ditelusuri ke baris tabel ini.
