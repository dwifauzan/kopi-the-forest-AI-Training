# Sistem Pakar Diagnosis Penyakit Tanaman Kopi

Forward Chaining + Certainty Factor, ditulis dari nol dengan Python standar (tanpa library tambahan). Dempster-Shafer dipakai sebagai metode pembanding. Spesifikasi lengkap ada di [`docs/specification.md`](docs/specification.md).

## Struktur folder (`model/`)

```
model/
├── main.py                  pintu masuk: menu + perintah CLI, hanya merangkai folder lain
├── basis_pengetahuan.json   satu-satunya sumber gejala, penyakit, aturan, skala CF
├── sistem_pakar/            OTAK sistem pakar, satu-satunya yang perlu dipakai web
│   ├── basis_pengetahuan.py   muat_kb(), periksa_kb(), daftar_pertanyaan()
│   ├── kontrak.py             validasi masukan + bentuk keluaran yang sama untuk CF dan DS
│   ├── inferensi.py           Forward Chaining + Certainty Factor: diagnosis()
│   └── dempster_shafer.py     pembanding Dempster-Shafer: diagnosis_ds()
├── antarmuka/
│   ├── terminal.py            tanya-jawab gejala dan cetak hasil (print/input hanya di sini)
│   └── api.py                 API JSON untuk frontend (docs/api.md), tanpa dependency
├── persiapan_data/          menyiapkan kasus uji
│   ├── lokasi.py              semua lokasi file di data/
│   ├── berkas_csv.py          baca/tulis CSV (aman untuk Excel: BOM dan pemisah ";")
│   ├── praproses.py           data mentah literatur -> data/bersih/kasus_literatur.csv
│   └── lembar_pakar.py        lembar kasus buta untuk pakar -> data/kasus_uji.csv
├── evaluasi/
│   ├── akurasi.py             CF dan DS pada kasus uji -> data/hasil_evaluasi.csv
│   └── black_box.py           skenario uji black box (spesifikasi B5)
├── tests/                   54 unit test (test_*.py)
├── data/                    data mentah, pemetaan, kasus uji, hasil evaluasi
└── docs/specification.md
```

Arah ketergantungan: `antarmuka/`, `persiapan_data/`, dan `evaluasi/` memakai `sistem_pakar/`; `sistem_pakar/` tidak memakai folder lain, jadi bisa disalin ke web apa adanya.

Urutan membaca untuk reviewer: `sistem_pakar/__init__.py` (kontrak), lalu `inferensi.diagnosis()`, `inferensi.forward_chaining()`, dan `dempster_shafer.diagnosis_ds()`. Setiap modul dan fungsi punya docstring yang menjelaskan tugasnya, parameter, nilai kembalian, dan error yang mungkin muncul.

## Isi penting

- `basis_pengetahuan.json`: 9 penyakit, 21 gejala, 27 aturan, 1 fakta antara, skala CF pengguna, dan ambang tampil. Data awal dari Tabel 4.1 skripsi Gatra Lanuari (UNEJ, 2017). R27 berstatus *usulan* dan belum divalidasi pakar. Isinya harus sama dengan [spreadsheet basis pengetahuan](https://claude.ai/artifact/Xg9FEWpRszRmJX9Ds9wXMS).
- `sistem_pakar.diagnosis({kode_gejala: cf_pengguna})`: diagnosis CF. `sistem_pakar.diagnosis_ds()` menerima masukan yang sama dan mengembalikan bentuk keluaran yang sama. `daftar_pertanyaan()` bisa dipakai web untuk menyusun form.
- `evaluasi/akurasi.py`: akurasi kedua metode dari kasus pakar (`data/kasus_uji.csv`) dan kasus literatur (`data/bersih/kasus_literatur.csv`), dilaporkan terpisah per sumber. Diagnosis yang seri ditulis `P05/P06/P07` dan dihitung tidak cocok.
- `persiapan_data/lembar_pakar.py`: lembar kasus "buta" (gejala saja, diagnosis kosong, urutan diacak) untuk diisi pakar. Lihat bagian "Mengumpulkan kasus uji dari pakar".
- `antarmuka/api.py`: API JSON untuk frontend Laravel (`python main.py api`). Endpoint, contoh controller Laravel, dan cara deploy ada di [`docs/api.md`](model/docs/api.md).
- `tests/`: 54 uji. Angka CF/DS dicocokkan dengan hitungan manual; uji praproses mengikuti isi data mentah.

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
python main.py lembar                                  # buat lembar kasus buta untuk pakar
python main.py impor-pakar                             # salin isian pakar ke data/kasus_uji.csv
python main.py api                                     # API JSON untuk frontend di http://127.0.0.1:5001
```

Semua perintah dijalankan dari folder `model/`. Unit test juga bisa lewat `python -m unittest -v`.


## Mengumpulkan kasus uji dari pakar

Diagnosis pada kasus uji harus dari pakar. Program hanya menyusun pertanyaannya.

1. `python main.py lembar` membuat `model/data/lembar_pakar/`:
   - `lembar_pakar.csv` + `PETUNJUK.md`: **berikan ke pakar**. Isinya 39 kombinasi gejala yang disusun dari basis pengetahuan, dengan urutan acak, kolom diagnosis kosong, dan tanpa hasil sistem.
   - `kunci_internal.csv`: **jangan diberikan ke pakar**. Berisi asal tiap kasus (khas, sebagian, lemah, negatif, gabungan, campuran, acak), untuk analisis di laporan.
2. Pakar mengisi `diagnosis_pakar` (kode P.., `-`, atau nama penyakit lain), `catatan`, dan identitas di baris pertama. Lembar bisa dibuka di Excel atau Google Sheets; simpan kembali sebagai CSV.
3. `python main.py impor-pakar [path_lembar.csv]` menyalin baris yang sudah diisi ke `data/kasus_uji.csv`. Kode kasus diberi awalan inisial pakar (`K01` → `BS-K01` untuk Budi Santoso), jadi lembar yang sama bisa diisi beberapa pakar. Kalau inisial dua pakar sama, pakai `--awalan`. Impor ulang aman (kode yang sudah ada dilewati). Lembar harus disimpan sebagai **CSV UTF-8**, bukan `.xlsx`.
4. `python main.py evaluasi` menghitung akurasi CF dan DS terhadap diagnosis pakar.

`python main.py lembar` menolak menimpa lembar yang sudah mulai diisi; pakai `--timpa` hanya kalau memang ingin membuat ulang.
Catatan untuk laporan: kasus disusun dari gejala di basis pengetahuan, jadi ada kemungkinan bias ke arah aturan yang sudah ada. Kasus `campuran` dan `acak` disertakan untuk menguranginya.

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
| `bersih/kasus_literatur.csv` | Hasil `persiapan_data/praproses.py`, siap dievaluasi (kode `L..`) |
| `bersih/ditolak.csv` | Baris mentah yang ditolak beserta alasannya |
| `kasus_uji.csv` | Kasus dari pakar (kode `K..`), diekspor dari sheet Kasus Uji |
| `hasil_evaluasi.csv` | Keluaran `evaluasi/akurasi.py`. Selalu ditimpa, jangan taruh data di sini |

Alurnya `python main.py praproses`, lalu `python main.py evaluasi`. Kalau data mentah bertambah atau berubah, sesuaikan tabel di `pemetaan/` (dan `KOLOM` di `persiapan_data/praproses.py` kalau nama kolomnya berbeda), bukan datanya. CF pengguna untuk kasus literatur ditetapkan 1,0 (`CF_LITERATUR`). Ini konvensi kelompok, bukan nilai dari sumber.

## Memakai dari frontend

Frontend (Laravel) memanggil API JSON: jalankan `python main.py api`, lalu ikuti [`docs/api.md`](model/docs/api.md) (endpoint, bentuk respons, contoh controller dan Blade, deploy).

Kalau aplikasi web ditulis dengan Python, paket `sistem_pakar` bisa dipanggil langsung:

```python
from sistem_pakar import METODE, daftar_pertanyaan, diagnosis, diagnosis_ds, muat_kb

kb = muat_kb()
out = diagnosis({"G01": 0.8, "G02": 0.6}, kb)   # atau diagnosis_ds(...); bentuk keluaran sama
```

Masukan yang salah (kode gejala tidak dikenal, CF bukan angka atau di luar 0..1) menghasilkan `ValueError` dengan pesan berbahasa Indonesia.
