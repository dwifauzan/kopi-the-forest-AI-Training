# Petunjuk pengisian lembar kasus

Lembar `lembar_pakar.csv` berisi 39 kasus. Setiap kasus adalah gejala yang dilihat
petani pada satu tanaman kopi, beserta seberapa yakin petani melihat gejala itu:

- **Mungkin**: Pengguna ragu gejala ini ada
- **Kemungkinan besar**: Gejala cukup jelas terlihat
- **Hampir pasti**: Gejala jelas, hampir yakin
- **Pasti**: Gejala terlihat jelas dan yakin

Gejala yang tidak disebut dianggap tidak terlihat atau tidak diketahui.

## Yang diisi
1. **diagnosis_pakar**: penyakit yang paling mungkin menurut Bapak/Ibu.
   - Tulis **kodenya** dari tabel di bawah, misalnya `P01`.
   - Tulis `-` kalau gejalanya belum cukup untuk menyimpulkan penyakit apa pun.
   - Kalau penyakitnya tidak ada di tabel, tulis **nama penyakitnya** langsung.
2. **catatan** (boleh kosong): alasan, kemungkinan penyakit lain, atau pemeriksaan tambahan yang perlu.
3. **nama_pakar, tanggal, lokasi**: cukup diisi di baris pertama.

Kolom `gejala` jangan diubah; kolom itu dibaca oleh program.
Mohon dinilai berdasarkan pengalaman Bapak/Ibu, tanpa melihat hasil aplikasi.

## Kode penyakit

| Kode | Nama | Penyebab |
|---|---|---|
| P01 | Karat daun kopi | Hemileia vastatrix |
| P02 | Bercak daun kopi | Cercospora coffeicola |
| P03 | Nematoda | Pratylenchus coffeae dan Radopholus similis |
| P04 | Jamur upas | Corticium salmonicolor |
| P05 | Jamur akar coklat | Phellinus noxius |
| P06 | Jamur akar hitam | Rosellinia sp. |
| P07 | Jamur akar putih | Rigidoporus sp. |
| P08 | Rebah batang kopi | Rhizoctonia solani |
| P09 | Busuk buah kopi | Fusarium sp. |
