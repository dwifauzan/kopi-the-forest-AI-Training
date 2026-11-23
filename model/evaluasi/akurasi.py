"""Evaluasi CF dan Dempster-Shafer terhadap diagnosis rujukan (pakar atau literatur).

Masukan (dibaca semua yang ada):
- data/kasus_uji.csv               : kasus dari pakar (kode K..), diekspor dari sheet Kasus Uji
- data/bersih/kasus_literatur.csv  : kasus literatur (kode L..), hasil praproses.py
  Kolom wajib: kode, gejala, diagnosis_pakar. Kolom lain boleh ada dan diabaikan.

Keluaran:
- data/hasil_evaluasi.csv: kolom sheet Hasil Evaluasi + "Metode" + "Sumber data".
  File ini SELALU DITIMPA; jangan simpan data di sini.

Aturan penilaian:
- Diagnosis sistem = penyakit teratas yang tampil (cf >= ambang). Tidak ada = "-".
- Kalau beberapa penyakit seri di puncak, ditulis "P05/P06/P07" dan dihitung tidak cocok.
- Akurasi dilaporkan terpisah per sumber. Untuk sumber literatur disebut
  "kesesuaian literatur", bukan akurasi lapangan.

    python main.py evaluasi [path_kasus.csv] [path_hasil.csv]
"""

import csv
import os

from persiapan_data.berkas_csv import baca_csv, kolom_csv
from persiapan_data.lokasi import HASIL_EVALUASI, KASUS_LITERATUR, KASUS_UJI
from sistem_pakar import METODE as SEMUA_METODE
from sistem_pakar import muat_kb, urai_gejala
from sistem_pakar.kontrak import diagnosis_teratas

SUMBER_KASUS = [KASUS_UJI, KASUS_LITERATUR]
HASIL = HASIL_EVALUASI

METODE = [(kode.upper(), fungsi) for kode, (_, fungsi) in SEMUA_METODE.items()]
KOLOM_HASIL = ["Kode kasus", "Diagnosis pakar", "Diagnosis sistem (kode)", "CF sistem (%)",
               "Cocok?", "Waktu respons (ms)", "Metode", "Sumber data"]
KOLOM_WAJIB = ["kode", "gejala", "diagnosis_pakar"]
SUMBER_LITERATUR = os.path.splitext(os.path.basename(KASUS_LITERATUR))[0]
PENANDA_CONTOH = "CONTOH_HAPUS"   # baris contoh dari spesifikasi A3, tidak ikut dihitung


def baca_kasus(path):
    """Baca satu file kasus. Setiap baris diberi kunci "_sumber" (nama file tanpa ekstensi).

    Baris tanpa kode diabaikan (misalnya baris kosong dari sheet). Pemisah ";" dari Excel dikenali.

    Error:
        ValueError kalau kolom wajib tidak ada.
    """
    sumber = os.path.splitext(os.path.basename(path))[0]
    baris = baca_csv(path)
    hilang = [k for k in KOLOM_WAJIB if k not in kolom_csv(path)]
    if hilang:
        raise ValueError(f"{path}: kolom wajib tidak ada: {', '.join(hilang)}")
    return [{**b, "_sumber": sumber} for b in baris if (b.get("kode") or "").strip()]


def berlabel(kasus):
    """True kalau kasus punya diagnosis rujukan dan bukan baris contoh."""
    rujukan = (kasus.get("diagnosis_pakar") or "").strip()
    return bool(rujukan) and PENANDA_CONTOH not in rujukan and PENANDA_CONTOH not in kasus["kode"]


def periksa_kasus(daftar_kasus, kb):
    """Cari kode kasus ganda dan diagnosis rujukan yang tidak ada di basis pengetahuan.

    Mengembalikan:
        daftar pesan peringatan (list of str).
    """
    peringatan = []
    dilihat = set()
    for k in daftar_kasus:
        if k["kode"] in dilihat:
            peringatan.append(f"Kode kasus {k['kode']} muncul lebih dari sekali")
        dilihat.add(k["kode"])
        rujukan = (k.get("diagnosis_pakar") or "").strip().upper()
        if berlabel(k) and rujukan != "-" and rujukan not in kb["penyakit"]:
            peringatan.append(f"{k['kode']}: diagnosis pakar '{rujukan}' tidak ada di basis pengetahuan, "
                              "pasti tidak cocok")
    return peringatan


def evaluasi(path_kasus=None, path_hasil=HASIL):
    """Jalankan kedua metode untuk setiap kasus, tulis CSV hasil, dan cetak ringkasan.

    Parameter:
        path_kasus: satu path, daftar path, atau None (= semua SUMBER_KASUS yang ada).
        path_hasil: lokasi CSV keluaran.

    Mengembalikan:
        (baris_hasil, ringkasan)
        - baris_hasil: list baris CSV, urut sesuai KOLOM_HASIL
        - ringkasan  : {(metode, sumber): {"benar", "dilabel", "seri", "total_ms", "jumlah"}}

    Error:
        ValueError kalau kolom wajib hilang atau format gejala salah (pesan menyebut kode kasus).
    """
    kb = muat_kb()
    if path_kasus is None:
        path_kasus = [p for p in SUMBER_KASUS if os.path.exists(p)]
    elif isinstance(path_kasus, str):
        path_kasus = [path_kasus]
    daftar_kasus = [k for p in path_kasus for k in baca_kasus(p)]
    peringatan = periksa_kasus(daftar_kasus, kb)

    masukan = {}
    for k in daftar_kasus:
        try:
            masukan[k["kode"]] = urai_gejala(k["gejala"])
        except ValueError as e:
            raise ValueError(f"Kasus {k['kode']} ({k['_sumber']}): {e}") from None

    baris_hasil = []
    ringkasan = {}
    for nama_metode, fungsi in METODE:
        for k in daftar_kasus:
            out = fungsi(masukan[k["kode"]], kb)
            sistem, persen, seri = diagnosis_teratas(out)
            rujukan = (k.get("diagnosis_pakar") or "").strip().upper()

            r = ringkasan.setdefault((nama_metode, k["_sumber"]),
                                     {"benar": 0, "dilabel": 0, "seri": 0, "total_ms": 0.0, "jumlah": 0})
            r["total_ms"] += out["waktu_ms"]
            r["jumlah"] += 1
            cocok = ""
            if berlabel(k):
                r["dilabel"] += 1
                r["seri"] += seri
                r["benar"] += sistem == rujukan
                cocok = "TRUE" if sistem == rujukan else "FALSE"

            baris_hasil.append([k["kode"], rujukan, sistem, persen, cocok, out["waktu_ms"],
                                nama_metode, k["_sumber"]])

    os.makedirs(os.path.dirname(path_hasil) or ".", exist_ok=True)
    with open(path_hasil, "w", encoding="utf-8", newline="") as f:
        tulis = csv.writer(f)
        tulis.writerow(KOLOM_HASIL)
        tulis.writerows(baris_hasil)

    cetak(baris_hasil, ringkasan, daftar_kasus, path_hasil, peringatan)
    return baris_hasil, ringkasan


def cetak(baris_hasil, ringkasan, daftar_kasus, path_hasil, peringatan=()):
    """Cetak tabel hasil per kasus, ringkasan per metode dan sumber, serta peringatan."""
    lebar = [15, 13, 12, 8, 6, 10, 6, 16]
    judul = ["Kasus", "Pakar", "Sistem", "CF (%)", "Cocok", "Waktu ms", "Metode", "Sumber"]
    print("  ".join(j.ljust(w) for j, w in zip(judul, lebar)))
    print("-" * (sum(lebar) + 2 * len(lebar)))
    for b in baris_hasil:
        print("  ".join(str(x).ljust(w) for x, w in zip(b, lebar)))
    print()

    for (metode, sumber), r in ringkasan.items():
        jenis = "kesesuaian literatur" if sumber == SUMBER_LITERATUR else "akurasi"
        if r["dilabel"]:
            nilai = f"{r['benar'] / r['dilabel'] * 100:.2f}% ({r['benar']}/{r['dilabel']})"
            if r["seri"]:
                nilai += f", {r['seri']} kasus seri dihitung tidak cocok"
        else:
            nilai = "belum ada kasus berlabel"
        print(f"{metode} [{sumber}]: {jenis} {nilai}, rata-rata waktu {r['total_ms'] / r['jumlah']:.3f} ms")

    for p in peringatan:
        print(f"Peringatan: {p}")
    if any(not berlabel(k) for k in daftar_kasus):
        print("Peringatan: ada kasus tanpa label pakar. Kasus itu tidak dihitung.")
    if not daftar_kasus:
        print("Belum ada kasus. Isi data/kasus_uji.csv dari sheet Kasus Uji atau jalankan praproses.py.")
    print(f"Hasil ditulis ke {path_hasil}")
