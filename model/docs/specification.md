# Sistem Pakar Diagnosis Penyakit Tanaman Kopi (Forward Chaining + Certainty Factor)

> **Untuk agent:** baca file ini sampai habis sebelum mengerjakan apa pun. Kerjakan tugas sesuai urutan di bagian "Daftar tugas". Setiap tugas punya kriteria selesai. Jangan menandai tugas selesai sebelum kriterianya terpenuhi dan `python -m unittest -v` lulus.

---

## 1. Konteks proyek

- **Mata kuliah:** Kecerdasan Buatan, Final Project, S1 Informatika Universitas Jember.
- **Tujuan:** website sistem pakar untuk membantu petani kopi dan penyuluh di Jember mendiagnosis penyakit tanaman kopi secara awal. Pengguna mencentang gejala yang terlihat dan memilih tingkat keyakinannya. Sistem lalu menampilkan penyakit, persentase keyakinan, dan cara penanganannya.
- **Kategori AI:** reasoning, yaitu sistem pakar berbasis aturan.
- **Metode:** Forward Chaining dan Certainty Factor, ditulis dari nol. Inovasinya adalah perbandingan dengan Dempster-Shafer.
- **Pengguna:** petani kopi skala kecil, penyuluh, dan pengawas kebun. Sistem dipakai untuk diagnosis per titik tanaman, bukan untuk memantau seluruh lahan. Kebanyakan pengguna membuka lewat HP.
- **Tenggat:** progress pada **23 November 2026**; presentasi final dan demo pada **30 November 2026**.

### Aturan keras (wajib dipatuhi)

1. **Tidak ada machine learning dan tidak ada training.** Jangan memakai scikit-learn, TensorFlow, PyTorch, model jadi, atau API AI. Mesin inferensi cukup memakai Python standar.
2. **Jangan mengarang data pakar.** Nilai CF, aturan baru, dan diagnosis pakar pada kasus uji hanya boleh berasal dari sumber (skripsi Gatra 2017) atau dari pakar. Kalau butuh nilai yang belum ada, beri tanda `TODO(pakar)` dan laporkan. Jangan menebak.
3. **Kontrak fungsi di bagian 4 dibekukan.** Nama fungsi, parameter, dan bentuk keluaran tidak boleh diubah, karena web dikerjakan orang lain secara paralel. Fungsi baru boleh ditambah.
4. **Basis pengetahuan hanya ada di satu tempat:** `basis_pengetahuan.json`. Web dan skrip lain harus membacanya dari file itu. Jangan menyalin daftar gejala atau penyakit ke HTML atau kode lain.
5. Teks yang dilihat pengguna ditulis dalam **Bahasa Indonesia**. Nama variabel dan fungsi boleh tetap memakai bahasa Indonesia, sesuai kode yang sudah ada.
6. Istilah di dokumen dan antarmuka: pakai "membangun model" atau "basis pengetahuan dan mesin inferensi", **jangan** "training model".

---

## 2. Keadaan sekarang (sudah selesai)

| File | Isi | Status |
|---|---|---|
| `basis_pengetahuan.json` | 9 penyakit (P01–P09), 21 gejala (G01–G21), 27 aturan (R01–R26 dari sumber, R27 usulan), 1 fakta antara (F01), skala CF pengguna, ambang tampil 0,2 | Selesai, menunggu validasi pakar |
| `sistem_pakar/inferensi.py` | Mesin Forward Chaining dan CF | Selesai |
| `sistem_pakar/dempster_shafer.py` | A2: pembanding Dempster-Shafer | Selesai |
| `sistem_pakar/basis_pengetahuan.py`, `sistem_pakar/kontrak.py` | Memuat/memeriksa KB; validasi masukan dan bentuk keluaran bersama | Selesai |
| `evaluasi/akurasi.py`, `evaluasi/black_box.py` | A3: evaluasi CF vs DS per sumber kasus (hasil seri ditangani); B5: skenario black box | Selesai; `data/kasus_uji.csv` (pakar) masih kosong |
| `persiapan_data/praproses.py`, `data/mentah/`, `data/pemetaan/`, `data/bersih/` | Praproses data literatur LeafNet: 12 baris mentah → 3 kasus (L01–L03), 7 ditolak | Selesai; kasus literatur bukan pengganti kasus pakar |
| `persiapan_data/lembar_pakar.py`, `data/lembar_pakar/` | Lembar kasus buta (39 kasus) untuk diisi pakar, lalu diimpor ke `data/kasus_uji.csv` | Selesai; menunggu pertemuan pakar |
| `antarmuka/terminal.py`, `main.py` | Mode terminal; pintu masuk tunggal semua fitur | Selesai |
| `tests/` | 44 uji, angka dicocokkan dengan hitungan manual | Semua lulus |

Struktur folder lengkap ada di `README.md` (bagian "Struktur folder"). Daftar tugas di bagian 5 ditulis sebelum struktur ini, jadi nama file di sana adalah nama lama.

**Spreadsheet basis pengetahuan** (7 sheet: Penyakit, Gejala, Aturan, Skala CF, Kasus Uji, Hasil Evaluasi, Sumber): https://claude.ai/artifact/Xg9FEWpRszRmJX9Ds9wXMS
Isinya sama dengan `basis_pengetahuan.json`. Kalau salah satunya diubah, yang lain harus ikut diubah.

Kalau ketiga file di atas belum ada di repo, berhenti dan minta file tersebut ke pengguna. Jangan menulis ulang dari nol.

---

## 3. Basis pengetahuan dan rumus

### Sumber data
Tabel 4.1 skripsi Gatra Lanuari (UNEJ, 2017), studi kasus Puslitkoka Jember. Kode P, G, dan R adalah penomoran kelompok, bukan kode dari skripsi.

### Skala CF pengguna
| Jawaban | Nilai |
|---|---|
| Tidak tahu | 0,0 (gejala diabaikan) |
| Mungkin | 0,4 |
| Kemungkinan besar | 0,6 |
| Hampir pasti | 0,8 |
| Pasti | 1,0 |

### Rumus CF
- Aturan satu premis: `CF = CF pakar × CF pengguna`
- Aturan premis DAN: `CF = MIN(CF semua premis) × CF pakar`
- Gabungan dua CF untuk kesimpulan yang sama:
  - keduanya ≥ 0: `CF1 + CF2 × (1 − CF1)`
  - keduanya < 0: `CF1 + CF2 × (1 + CF1)`
  - beda tanda: `(CF1 + CF2) / (1 − MIN(|CF1|, |CF2|))`
- Rumus lengkap ini wajib dipakai karena ada **CF pakar negatif**: R05 (G05 → P02, −0,4) dan R09 (G08 → P03, −0,6).

### Forward Chaining
Working memory diisi dengan gejala yang CF penggunanya lebih dari 0. Mesin lalu menembakkan setiap aturan yang semua premisnya terpenuhi, dan kesimpulannya masuk ke working memory. Proses berulang sampai tidak ada aturan baru yang bisa jalan. Aturan yang memakai fakta antara menunggu sampai CF fakta itu final.

**R27** (`G12 DAN G13 → F01 Gangguan sistem perakaran`, status usulan): P05, P06, dan P07 punya gejala daun yang sama persis, sehingga nilainya seri kalau hanya G12 dan G13 yang dipilih. F01 membuat sistem menyarankan pengguna memeriksa akar (G14, G15, G16). Nilai CF 0,8 untuk R27 masih menunggu penilaian pakar.

### Contoh hitungan (dipakai di slide dan tes)
Masukan G01 = 0,8, G02 = 0,6, G03 = 0,4:
- R01: 0,8 × 0,8 = 0,64
- R02: 0,6 × 0,6 = 0,36 → 0,64 + 0,36 × 0,36 = 0,7696
- R03: 0,4 × 0,4 = 0,16 → 0,7696 + 0,16 × 0,2304 = 0,8065 → **Karat daun 80,65%**
- R07: 0,6 × 0,6 = 0,36 → Nematoda 36%

---

## 4. Kontrak fungsi (DIBEKUKAN)

```python
from sistem_pakar import diagnosis, muat_kb      # dulu: from inferensi import ...

kb = muat_kb()                                   # isi basis_pengetahuan.json
out = diagnosis({"G01": 0.8, "G02": 0.6}, kb)    # {kode_gejala: cf_pengguna}
```

Bentuk keluaran `diagnosis()`:
```python
{
  "hasil": [   # urut dari CF tertinggi; berisi juga penyakit dengan CF negatif
    {"kode": "P01", "nama": "Karat daun kopi", "cf": 0.7696,
     "persen": 76.96, "solusi": "...", "tampil": True},   # tampil = cf >= ambang_tampil
  ],
  "fakta_antara": [{"kode": "F01", "nama": "...", "cf": 0.64, "saran": "..."}],
  "jejak": ["Fakta awal: ...", "[1] R01: JIKA G01 MAKA P01 | CF = 0.8 x 0.8 = 0.64"],
  "aturan_jalan": ["R01", "R02"],
  "waktu_ms": 0.06
}
```

Untuk membuat form, web membaca `kb["gejala"]` (setiap gejala punya `nama` dan `bagian`) dan `kb["skala_cf_pengguna"]`.

Setiap metode baru (misalnya Dempster-Shafer) **harus mengembalikan bentuk yang sama**, supaya web cukup mengganti nama fungsinya.

---

## 5. Daftar tugas

Kerjakan berurutan. Bagian A adalah model AI (dikerjakan pemilik repo). Bagian B adalah web (bisa diserahkan ke anggota lain, dan bisa dikerjakan paralel dengan A karena kontraknya sudah beku).

### A. Model AI

#### A1. Rapikan repo
- Buat struktur berikut:
  ```
  basis_pengetahuan.json
  inferensi.py
  dempster_shafer.py        (A2)
  evaluasi.py               (A3)
  test_inferensi.py
  test_dempster_shafer.py   (A2)
  data/kasus_uji.csv        (A3)
  app.py, templates/, static/   (B)
  requirements.txt
  docs/
  ```
- Buat `requirements.txt` yang hanya berisi `flask` (dan `gunicorn` kalau deploy ke Render).
- **Selesai jika:** `python -m unittest -v` lulus dan `python main.py diagnosis` jalan.

#### A2. Dempster-Shafer sebagai pembanding (inovasi)
Buat `dempster_shafer.py` berisi fungsi `diagnosis_ds(input_pengguna, kb=None)` dengan bentuk keluaran yang sama seperti `diagnosis()`. Pakai `basis_pengetahuan.json` yang sama, tanpa data baru.

Spesifikasinya:
- Θ adalah himpunan semua penyakit (P01–P09).
- Untuk setiap gejala g yang dipilih dengan CF pengguna u:
  - S_g adalah himpunan penyakit yang punya aturan **positif** satu-premis dengan g. Nilai CF pakar untuk g sama di semua penyakit di S_g (contoh: G12 bernilai 0,6 untuk P05, P06, P07), jadi densitasnya `d = CF pakar × u`.
  - Fungsi massa: `m(S_g) = d`, `m(Θ) = 1 − d`.
  - Untuk aturan **negatif** (R05, R09): `m(Θ \ {p}) = |CF pakar| × u`, sisanya ke Θ.
  - Kalau CF pakar untuk g ternyata berbeda di antara penyakit dalam S_g, pakai nilai maksimumnya, lalu catat di `jejak`.
- Gabungkan semua fungsi massa satu per satu dengan aturan kombinasi Dempster. Konflik K (massa pada irisan kosong) dinormalisasi dengan membagi `1 − K`. Kalau K = 1, kembalikan hasil kosong dan beri catatan konflik total di `jejak`.
- Abaikan R27 dan fakta antara. `fakta_antara` dikembalikan sebagai `[]`.
- Skor per penyakit memakai pignistic probability: `BetP(p) = Σ m(A)/|A|` untuk setiap himpunan fokus A yang memuat p (termasuk Θ). Isi `cf` dengan BetP, dan `persen` dengan BetP × 100 dibulatkan 2 angka.
- `jejak` mencatat setiap fungsi massa, hasil kombinasi per langkah, dan nilai K.
- Tambah kunci opsional `"himpunan_terkuat": {"anggota": [...], "massa": x}` (kunci tambahan boleh, kunci lama tidak boleh berubah).

Uji minimal di `test_dempster_shafer.py` (angka berikut sudah dihitung manual):
- G01 = 0,8 → m{P01} = 0,64, m(Θ) = 0,36, BetP(P01) = 0,64 + 0,36/9 = **0,68**.
- G12 = 0,8, G13 = 0,8 → m{P05,P06,P07} = 0,8128, m(Θ) = 0,1872, BetP(P05) = 0,8128/3 + 0,1872/9 ≈ **0,2917**.
- Masukan kosong → `hasil == []`.
- Kombinasi dua massa yang saling bertentangan (misal G01 dan G17, keduanya pasti) → K > 0 dan jumlah semua massa setelah normalisasi = 1.

**Selesai jika:** semua uji lulus dan `diagnosis_ds()` bisa dipanggil dengan masukan yang sama seperti `diagnosis()`.

#### A3. Skrip evaluasi akurasi
Kasus uji diisi bersama pakar di sheet Kasus Uji, lalu diekspor ke `data/kasus_uji.csv` dengan kolom:
```
kode,gejala,diagnosis_pakar
K01,"G01=0.8; G02=0.6",P01
```
Buat `evaluasi.py` yang:
- membaca CSV tersebut;
- menjalankan `diagnosis()` dan `diagnosis_ds()` untuk setiap kasus. Diagnosis sistem adalah penyakit teratas yang `tampil == True`; kalau tidak ada, isi `-`;
- mencatat kode penyakit teratas, persennya, cocok atau tidak dengan diagnosis pakar, dan `waktu_ms`;
- mencetak tabel ringkas serta akurasi kedua metode, dan menulis `data/hasil_evaluasi.csv` dengan kolom yang sama seperti sheet Hasil Evaluasi (kode kasus, diagnosis pakar, diagnosis sistem, CF sistem (%), cocok, waktu respons (ms)), satu file per metode atau dengan kolom `metode`.

**Jangan membuat kasus uji sendiri.** Kalau `data/kasus_uji.csv` belum ada, buat file contoh berisi baris kepala saja dan dua baris yang ditandai `CONTOH_HAPUS`, lalu laporkan bahwa data dari pakar masih ditunggu.

**Selesai jika:** skrip jalan pada file contoh dan menghasilkan CSV keluaran.

#### A4. Sinkronisasi setelah validasi pakar
Setelah pakar memvalidasi (status di sheet Aturan berubah):
- perbarui `basis_pengetahuan.json` (nilai `cf` dan `status`: `sumber`, `usulan`, atau `divalidasi`);
- kalau ada nilai yang berubah, perbarui angka harapan di tes beserta komentar hitungan manualnya;
- jalankan semua tes.

### B. Website (dapat diserahkan ke tim web)

#### B1. Aplikasi Flask (`app.py`)
Rute:
| Rute | Fungsi |
|---|---|
| `GET /` | Beranda: penjelasan singkat, tombol "Mulai diagnosis", catatan bahwa hasil hanya diagnosis awal dan sebaiknya dikonfirmasi ke penyuluh |
| `GET /diagnosis` | Form gejala |
| `POST /diagnosis` | Memproses form, memanggil `diagnosis()` (atau `diagnosis_ds()` kalau `metode=ds`), lalu menampilkan hasil |
| `GET /tentang` | Metode, rumus, sumber data, anggota kelompok |
| `GET /api/gejala`, `POST /api/diagnosis` | JSON (opsional, berguna untuk uji black box) |

#### B2. Form gejala (harus nyaman di HP)
- Kelompokkan gejala berdasarkan `bagian` (Daun, Tajuk, Batang/cabang, Akar, Bunga/buah) dalam bentuk accordion atau kartu.
- Setiap gejala punya pilihan dari `skala_cf_pengguna`, dengan nilai bawaan "Tidak tahu". Pakai radio button atau select; jangan memakai slider.
- Kalau semua gejala bernilai "Tidak tahu", tampilkan pesan dan jangan memproses.
- Bootstrap 5 lewat CDN, tanpa build tool. Target lebar layar 360 px.

#### B3. Halaman hasil
- Kartu utama: nama penyakit teratas, persen besar, progress bar, dan penanganan.
- Daftar penyakit lain yang `tampil == True`.
- Kalau `fakta_antara` tidak kosong, tampilkan kotak peringatan berisi `saran`.
- Kalau tidak ada yang tampil: "Gejala belum cukup untuk menyimpulkan penyakit. Tambah gejala atau hubungi penyuluh."
- Bagian lipat "Lihat langkah perhitungan" berisi `jejak` (ini fasilitas penjelasan sistem pakar).
- Tampilkan `waktu_ms` dengan huruf kecil.
- Tombol "Diagnosis ulang".

#### B4. Deploy
- Utamakan **PythonAnywhere** (gratis, cocok untuk Flask, tidak tidur). Alternatifnya Render dengan `gunicorn app:app`.
- Selesaikan deploy paling lambat **27 November**.
- Catat setiap langkahnya beserta tangkapan layar di `docs/deploy.md`.

#### B5. Uji black box
Buat `docs/uji_black_box.md`: tabel berisi skenario, masukan, hasil yang diharapkan, hasil sebenarnya, dan status. Minimal mencakup:
semua gejala "Tidak tahu"; satu gejala; kasus karat daun di bagian 3 (harus 80,65%); G04 pasti dan G05 hampir pasti (harus 70,59%, menguji CF negatif); hanya G08 (tidak ada penyakit yang tampil); G12 dan G13 (muncul saran periksa akar); G12, G13, dan G16 (jamur akar putih teratas); serta perpindahan metode ke DS.

---

## 6. Jadwal

| Tanggal | Target |
|---|---|
| 21–22 Nov | A1 selesai; demo terminal siap; slide progress |
| **23 Nov** | **Presentasi progress** |
| 24–26 Nov | A2, A3; B1–B3; validasi pakar dan pengumpulan kasus uji; integrasi web dengan model paling lambat 26 Nov |
| 27 Nov | B4 deploy; A4 kalau validasi pakar sudah ada |
| 28 Nov | Evaluasi (A3 dengan data pakar, B5, kuesioner pengguna); **pembekuan fitur** |
| 29 Nov | Laporan akhir, slide final, log bimbingan, latihan demo dari link online dan cadangan demo terminal |
| **30 Nov** | **Presentasi final dan demo** |

---

## 7. Cara menjalankan

```bash
python main.py                 # menu semua fitur (jalankan dari folder model/)
python main.py diagnosis       # diagnosis lewat terminal
python main.py tes             # semua tes (atau python -m unittest -v)
python main.py evaluasi        # evaluasi akurasi
flask --app app run --debug    # website lokal (setelah B1)
```

## 8. Sumber

1. Gatra Lanuari (2017). *Penerapan Sistem Pakar untuk Penentuan Penyakit Tanaman Kopi Menggunakan Metode Certainty Factor (Studi Kasus: Puslitkoka Jember).* Skripsi, Universitas Jember. Data awal.
2. Evi Miftahul Rohmah (2026). *CekKopi: Implementasi Metode Certainty Factor pada Sistem Pakar Diagnosa Hama dan Penyakit Tanaman Kopi.* Politeknik Negeri Jember. Pembanding.
3. Jurnal Explore, Universitas Bandar Lampung (2020). Sistem pakar hama dan penyakit kopi (BFS + CF). Pembanding.
4. Validasi pakar: nama, instansi, dan tanggal diisi setelah pertemuan.
