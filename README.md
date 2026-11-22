# Sistem Pakar Diagnosis Penyakit Tanaman Kopi

Forward Chaining + Certainty Factor, ditulis dari nol dengan Python standar (tanpa library tambahan). Dempster-Shafer dipakai sebagai metode pembanding. Spesifikasi lengkap ada di [`docs/specification.md`](docs/specification.md).

## File

- `basis_pengetahuan.json`: 9 penyakit, 21 gejala, 27 aturan, 1 fakta antara, skala CF pengguna, dan ambang tampil. Data awal dari Tabel 4.1 skripsi Gatra Lanuari (UNEJ, 2017). R27 berstatus *usulan* dan belum divalidasi pakar. Isinya harus sama dengan [spreadsheet basis pengetahuan](https://claude.ai/artifact/Xg9FEWpRszRmJX9Ds9wXMS).
- `inferensi.py`: mesin inferensi. Fungsi utama `diagnosis({kode_gejala: cf_pengguna})`.
- `dempster_shafer.py`: pembanding Dempster-Shafer. Fungsi `diagnosis_ds()` menerima masukan dan mengembalikan bentuk keluaran yang sama.
- `praproses.py`: menyaring data mentah menjadi kasus uji siap pakai.
- `main.py`: pintu masuk tunggal (menu dan perintah) untuk semua fitur di bawah.
- `evaluasi.py`: menghitung akurasi kedua metode dari kasus pakar (`data/kasus_uji.csv`) dan kasus literatur (`data/bersih/kasus_literatur.csv`), dilaporkan terpisah per sumber. Diagnosis yang seri ditulis `P05/P06/P07` dan dihitung tidak cocok. Hasilnya ditulis ke `data/hasil_evaluasi.csv`.
- `test_inferensi.py`, `test_dempster_shafer.py`: 20 uji yang dicocokkan dengan hitungan manual.
- `test_praproses.py`, `test_evaluasi.py`: 11 uji praproses dan evaluasi. Harapannya diambil dari isi data mentah.
- `test_inferensi.py` juga memuat 4 uji yang memastikan pertanyaan gejala selalu mengikuti isi basis pengetahuan.

## Cara menjalankan

Semua fitur bisa dijalankan dari `main.py` (di macOS pakai `python3`):

```bash
python main.py                                         # menu interaktif
python main.py diagnosis                               # tanya-jawab gejala (CF)
python main.py diagnosis --metode ds                   # tanya-jawab gejala (Dempster-Shafer)
python main.py diagnosis --gejala "G01=0.8; G02=0.6" --metode keduanya
python main.py bandingkan                              # tanya-jawab, hasil CF dan DS berdampingan
python main.py tes                                     # unit test
python main.py blackbox                                # skenario uji black box (spesifikasi B5)
python main.py praproses                               # data mentah -> data/bersih/kasus_literatur.csv
python main.py evaluasi                                # akurasi (kasus pakar + kasus literatur)
python main.py kb                                      # lihat isi basis pengetahuan
python main.py cek                                     # periksa kesesuaian basis pengetahuan, pertanyaan, dan pemetaan
```

Modul tetap bisa dijalankan sendiri: `python inferensi.py`, `python dempster_shafer.py`, `python evaluasi.py`, `python -m unittest -v`.

## Rumus Certainty Factor

- CF premis = min(CF semua premis), untuk aturan dengan premis DAN
- CF aturan = CF premis x CF pakar (aturan 1 premis: CF pakar x CF pengguna)
- Gabungan dua CF:
  - keduanya >= 0: CF1 + CF2 x (1 - CF1)
  - keduanya < 0: CF1 + CF2 x (1 + CF1)
  - beda tanda: (CF1 + CF2) / (1 - min(|CF1|, |CF2|))

Rumus lengkap ini diperlukan karena data pakar memuat CF negatif (R05 = -0,4 dan R09 = -0,6).

## Bagian Forward Chaining

Working memory diisi dengan gejala yang dipilih pengguna. Mesin lalu menembakkan aturan yang semua premisnya terpenuhi, dan kesimpulannya masuk ke working memory. Proses berulang sampai tidak ada aturan baru yang bisa jalan. Aturan yang memakai fakta antara menunggu sampai CF fakta itu final.

R27 (`G12 DAN G13 -> F01 Gangguan sistem perakaran`) menghasilkan fakta antara. Jamur akar coklat, hitam, dan putih punya dua gejala daun yang sama persis, sehingga tanpa gejala akar nilai ketiganya seri. Dalam kasus itu sistem menyarankan pengguna memeriksa akar.

## Dempster-Shafer

- Θ = semua penyakit. Setiap gejala g dengan CF pengguna u memberi m(S_g) = CF pakar x u, sisanya ke Θ. S_g adalah himpunan penyakit yang punya aturan positif satu premis dengan g.
- Aturan negatif (R05, R09) memberi massa ke Θ \ {p}.
- Massa digabung dengan aturan kombinasi Dempster, dan konflik K dinormalisasi dengan 1 - K.
- Skor tiap penyakit dihitung dengan pignistic probability BetP(p) = jumlah m(A)/|A|.
- R27 dan fakta antara diabaikan.

## Data dan evaluasi

Semua file di bawah ada di `model/data/`:

| Path | Isi |
|---|---|
| `mentah/leafnet_coffee_kb.csv` | Data mentah LeafNet (12 baris), disimpan apa adanya. Jangan diedit |
| `pemetaan/penyakit.csv` | Label penyakit di sumber → kode P. `-` = sehat, kosong = di luar cakupan |
| `pemetaan/gejala.csv` | Pola teks (regex) → kode G |
| `bersih/kasus_literatur.csv` | Hasil `praproses.py`, siap dievaluasi (kode `L..`) |
| `bersih/ditolak.csv` | Baris mentah yang ditolak beserta alasannya |
| `kasus_uji.csv` | Kasus dari pakar (kode `K..`), diekspor dari sheet Kasus Uji |
| `hasil_evaluasi.csv` | Keluaran `evaluasi.py`. Selalu ditimpa, jangan taruh data di sini |

Alurnya `python main.py praproses`, lalu `python main.py evaluasi`. Kalau data mentah bertambah atau berubah, sesuaikan tabel di `pemetaan/` (dan `KOLOM` di `praproses.py` kalau nama kolomnya berbeda), bukan datanya. CF pengguna untuk kasus literatur ditetapkan 1,0 (`CF_LITERATUR`). Ini konvensi kelompok, bukan nilai dari sumber.

## Memakai di Flask

```python
from inferensi import diagnosis, muat_kb
from dempster_shafer import diagnosis_ds

kb = muat_kb()
out = diagnosis({"G01": 0.8, "G02": 0.6}, kb)   # atau diagnosis_ds(...)
out["hasil"]          # daftar penyakit urut CF, dengan persen, solusi, dan tampil
out["fakta_antara"]   # saran tambahan, misalnya periksa akar
out["jejak"]          # langkah penalaran untuk fasilitas penjelasan
out["waktu_ms"]       # untuk evaluasi waktu respons
kb["gejala"]          # {kode: {nama, bagian}} untuk membuat form
kb["skala_cf_pengguna"]
```

Kode gejala yang tidak dikenal, atau CF di luar 0..1, menghasilkan `ValueError`. Tangkap error ini di rute API dan kembalikan status 400.
