# Hasil evaluasi (dibuat otomatis oleh `python -m ml evaluate`)

**Data:** produksi nyata La Réunion (Okt 2021–Apr 2023), radiasi satelit SARAH3, suhu/angin ERA5.
**Periode uji:** Feb–Mei 2022 (1170 jam, tidak dipakai melatih). Gangguan **disuntikkan**, kecuali baris bayangan nyata.

## Akurasi produksi seharusnya (MAE per kapasitas, data uji)

|                 |    mae |
|:----------------|-------:|
| pvlib           | 0.0888 |
| pvlib + XGBoost | 0.0688 |

Out-of-fold data latih: pvlib 0.0923, pvlib + XGBoost 0.0630.

## Perbandingan detektor

|                        |   Threshold tetap 20% |   Threshold tetap, alarm palsu disamakan |   pvlib + XGBoost, aturan 2 jam |   pvlib + CUSUM |   pvlib + XGBoost + CUSUM (usulan) |   Pembanding unit tetangga + CUSUM |   Sensor di lokasi + CUSUM (batas atas) |
|:-----------------------|----------------------:|-----------------------------------------:|--------------------------------:|----------------:|-----------------------------------:|-----------------------------------:|----------------------------------------:|
| alarm_palsu_per_minggu |                  0.62 |                                     0.5  |                            0.19 |            0.25 |                               0.38 |                               0.25 |                                    0.5  |
| per_minggu_cerah       |                  0.18 |                                     0.09 |                            0.09 |            0.26 |                               0.35 |                               0.35 |                                    0.61 |
| per_minggu_mendung     |                  1.75 |                                     1.53 |                            0.44 |            0.22 |                               0.44 |                               0    |                                    0.22 |
| cable_cut              |                  1    |                                     1    |                            1    |            0.95 |                               0.95 |                               0.9  |                                    0.75 |
| loose_connector        |                  0.35 |                                     0.4  |                            0.1  |            0.35 |                               0.5  |                               0.7  |                                    0.8  |
| partial_shading        |                  0.2  |                                     0.15 |                            0    |            0.35 |                               0.55 |                               1    |                                    1    |
| soiling                |                  0.03 |                                     0.03 |                            0.07 |            0.77 |                               0.93 |                               1    |                                    1    |
| bayangan_nyata         |                  0.09 |                                     0.09 |                            0.09 |            0.43 |                               0.39 |                               0.96 |                                    0.83 |
| delay_median_jam       |                  1    |                                     1    |                            1    |           55    |                              49    |                              13.5  |                                   19    |

Kolom pola = recall per kejadian. Alarm yang juga muncul di salinan tanpa gangguan tidak dihitung.

## Hasil per skenario (untuk `docs/tabel_uji.md`)

| pattern         |   variant | method   |   kejadian |   terdeteksi |   delay_median_jam |   penyebab_benar |
|:----------------|----------:|:---------|-----------:|-------------:|-------------------:|-----------------:|
| cable_cut       |         1 | tetangga |         10 |            8 |                0   |         1        |
| cable_cut       |         1 | usulan   |         10 |           10 |                0   |         1        |
| cable_cut       |         2 | tetangga |         10 |           10 |                0   |         1        |
| cable_cut       |         2 | usulan   |         10 |            9 |                0   |         1        |
| loose_connector |         1 | tetangga |         10 |            4 |               15.5 |         0        |
| loose_connector |         1 | usulan   |         10 |            3 |               29   |         0.333333 |
| loose_connector |         2 | tetangga |         10 |           10 |               23.5 |         0.3      |
| loose_connector |         2 | usulan   |         10 |            7 |               28   |         0.428571 |
| partial_shading |         1 | tetangga |         10 |           10 |               22   |         0.1      |
| partial_shading |         1 | usulan   |         10 |            5 |               26   |         0.4      |
| partial_shading |         2 | tetangga |         10 |           10 |               11.5 |         0.3      |
| partial_shading |         2 | usulan   |         10 |            6 |               70.5 |         0.5      |
| soiling         |         1 | tetangga |         10 |           10 |               49.5 |         0        |
| soiling         |         1 | usulan   |         10 |            9 |              221   |         0.333333 |
| soiling         |         2 | tetangga |         10 |           10 |               26.5 |         0        |
| soiling         |         2 | usulan   |         10 |            9 |              125   |         0.222222 |
| soiling         |         3 | tetangga |         10 |           10 |                1   |         0        |
| soiling         |         3 | usulan   |         10 |           10 |               89.5 |         0.5      |

## Bayangan nyata per jenis label

|   code | method         |   hari |   terdeteksi |
|-------:|:---------------|-------:|-------------:|
|    1   | tetangga       |      2 |            2 |
|    1   | threshold_adil |      2 |            2 |
|    1   | usulan         |      2 |            2 |
|    2.1 | tetangga       |      1 |            1 |
|    2.1 | threshold_adil |      1 |            0 |
|    2.1 | usulan         |      1 |            0 |
|    2.2 | tetangga       |      1 |            1 |
|    2.2 | threshold_adil |      1 |            0 |
|    2.2 | usulan         |      1 |            0 |
|    2.3 | tetangga       |      1 |            1 |
|    2.3 | threshold_adil |      1 |            0 |
|    2.3 | usulan         |      1 |            0 |
|    3.1 | tetangga       |      3 |            3 |
|    3.1 | threshold_adil |      3 |            0 |
|    3.1 | usulan         |      3 |            0 |
|    3.2 | tetangga       |      4 |            3 |
|    3.2 | threshold_adil |      4 |            0 |
|    3.2 | usulan         |      4 |            0 |
|    4   | tetangga       |     11 |           11 |
|    4   | threshold_adil |     11 |            0 |
|    4   | usulan         |     11 |            7 |

## Uji aturan baterai melemah (data nyata BBOXX, 27 baterai)

Baterai yang akhirnya masuk perbaikan dan tertandai dalam 30 hari terakhir: 10 dari 25.
Baterai yang masih hidup dan tertandai: 0 dari 2.
