# Sistem Pakar Diagnosis Penyakit Tanaman Kopi

Forward Chaining + Certainty Factor, ditulis dari nol dengan Python standar (tanpa library tambahan).

## File

- `basis_pengetahuan.json`: 9 penyakit, 21 gejala, 27 aturan, skala CF pengguna, ambang tampil. Data awal dari Tabel 4.1 skripsi Gatra Lanuari (UNEJ, 2017). R27 berstatus *usulan* dan belum divalidasi pakar.
- `inferensi.py`: mesin inferensi. Fungsi utama `diagnosis({kode_gejala: cf_pengguna})`.
- `test_inferensi.py`: 11 uji yang dicocokkan dengan hitungan manual.

## Cara menjalankan

```bash
python inferensi.py          # mode tanya-jawab di terminal (untuk demo progress)
python -m unittest -v        # jalankan pengujian
```

## Rumus

- CF premis = min(CF semua premis), untuk aturan dengan premis DAN
- CF aturan = CF premis x CF pakar (aturan 1 premis: CF pakar x CF pengguna)
- Gabungan dua CF:
  - keduanya >= 0: CF1 + CF2 x (1 - CF1)
  - keduanya < 0: CF1 + CF2 x (1 + CF1)
  - beda tanda: (CF1 + CF2) / (1 - min(|CF1|, |CF2|))

Rumus lengkap ini diperlukan karena data pakar memuat CF negatif (R05 = -0,4 dan R09 = -0,6).

## Bagian Forward Chaining

Working memory diisi dengan gejala yang dipilih pengguna. Mesin lalu menembakkan aturan yang semua premisnya terpenuhi, dan kesimpulannya masuk ke working memory. Proses berulang sampai tidak ada aturan baru yang bisa jalan.

R27 (`G12 DAN G13 -> F01 Gangguan sistem perakaran`) menghasilkan fakta antara. Jamur akar coklat, hitam, dan putih punya dua gejala daun yang sama persis, sehingga tanpa gejala akar nilai ketiganya seri. Dalam kasus itu sistem menyarankan pengguna memeriksa akar.

## Memakai di Flask

```python
from inferensi import diagnosis
out = diagnosis({"G01": 0.8, "G02": 0.6})
out["hasil"]        # daftar penyakit urut CF, dengan persen dan solusi
out["jejak"]        # langkah penalaran untuk fasilitas penjelasan
out["waktu_ms"]     # untuk evaluasi waktu respons
```
