# Sumber data

Setiap angka di proposal harus bisa ditelusuri ke tabel ini.

| Data | Sumber | Rentang | Lisensi | Label |
|---|---|---|---|---|
| Produksi PV + bayangan berlabel | Graillet dkk. 2023, *Data in Brief* 46:108723. Zenodo [10.5281/zenodo.7157424](https://doi.org/10.5281/zenodo.7157424) | 1 Okt 2021–13 Apr 2023 | CC BY 4.0 | NYATA, diskalakan ke 50 Wp |
| Radiasi satelit historis | Open-Meteo Satellite API, model `eumetsat_sarah3` (EUMETSAT CM SAF SARAH-3) | sama | Non-komersial, wajib sitasi | NYATA |
| Radiasi satelit terbaru (Indonesia) | Open-Meteo Satellite API (JMA/JAXA Himawari) | live | Non-komersial, wajib sitasi | NYATA |
| Suhu, angin, awan, hujan | Open-Meteo Historical Weather API (ERA5) | sama | Non-komersial, wajib sitasi Open-Meteo + Copernicus | NYATA |
| Rekaman baterai | Aitio & Howey 2021, Oxford ORA, DOI 10.5287/bodleian:aVR4oDV4N, [arXiv:2107.13856](https://arxiv.org/abs/2107.13856). 27 baterai (`set_10.zip`) | 400–760 hari per baterai | CC BY-NC 4.0 (non-komersial) | NYATA, sistem berbeda dari panel |
| Gangguan | `ml/evaluation/faults.py`, parameter `ml/config.yaml` | — | buatan | SUNTIKAN |

**Pemilihan sumber radiasi (diuji 4 Nov 2026):** terhadap sensor La Réunion, SARAH3 berkorelasi 0,86 dan ERA5 0,81 pada ±6.000 jam siang.

**Kaggle "Solar Power Generation Data" tidak dipakai:** lisensinya "Data files © Original Authors", bukan lisensi terbuka, dan lokasinya tidak diketahui.

**Tarif:** P-3/TR Rp1.699,53/kWh. Sumber berita ([Kompas TV](https://www.kompas.tv/info-publik/678125/update-tarif-listrik-pln-1-juli-2026-cek-harga-per-kwh-semua-golongan)), tarif triwulan IV 2026 tidak naik. Perlu dikonfirmasi ke halaman tarif PLN.

