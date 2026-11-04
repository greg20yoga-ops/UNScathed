# Hasil evaluasi (dibuat otomatis oleh `python -m model.run`)

**Sumber data:** SINTETIS (cuaca + produksi buatan)

Gangguan **disuntikkan buatan** ke bagian uji (data publik tidak berlabel gangguan).
Pembagian latih/uji berdasarkan waktu. Hari mendung = 30% hari uji dengan energi POA terendah.

## Ringkasan per metode (tanpa gangguan = ukur alarm palsu; dengan gangguan = ukur deteksi)
| metode    |   alarm_palsu/minggu |   presisi_alarm |   alarm_palsu_hari_mendung |   recall |   median_delay_jam |
|:----------|---------------------:|----------------:|---------------------------:|---------:|-------------------:|
| threshold |                  3.2 |            0.86 |                         18 |      1   |               35   |
| pvlib     |                  0   |            1    |                          0 |      0.9 |               17   |
| pvlib_ml  |                  0   |            1    |                          0 |      0.8 |               16.5 |

## Recall per pola gangguan
| pattern         |   threshold |    pvlib |   pvlib_ml |
|:----------------|------------:|---------:|-----------:|
| cable_cut       |           1 | 1        |   1        |
| derating        |           1 | 0.666667 |   0.333333 |
| partial_shading |           1 | 1        |   1        |
| soiling         |           1 | 1        |   1        |

## Akurasi tebakan penyebab (metode pvlib_ml)
| pattern         |   akurasi_tebakan_penyebab |
|:----------------|---------------------------:|
| cable_cut       |                          1 |
| derating        |                          0 |
| partial_shading |                          1 |
| soiling         |                          1 |

> Catatan jujur: bila `pvlib_ml` tidak lebih baik dari `pvlib`, laporkan apa adanya dan cari sebabnya.
