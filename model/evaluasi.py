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

    python evaluasi.py [path_kasus.csv] [path_hasil.csv]
"""

import csv
import os
import re
import sys

from dempster_shafer import diagnosis_ds
from inferensi import diagnosis, muat_kb

FOLDER = os.path.dirname(os.path.abspath(__file__))
KASUS_UJI = os.path.join(FOLDER, "data", "kasus_uji.csv")
KASUS_LITERATUR = os.path.join(FOLDER, "data", "bersih", "kasus_literatur.csv")
SUMBER_KASUS = [KASUS_UJI, KASUS_LITERATUR]
HASIL = os.path.join(FOLDER, "data", "hasil_evaluasi.csv")

METODE = [("CF", diagnosis), ("DS", diagnosis_ds)]
KOLOM_HASIL = ["Kode kasus", "Diagnosis pakar", "Diagnosis sistem (kode)", "CF sistem (%)",
               "Cocok?", "Waktu respons (ms)", "Metode", "Sumber data"]
KOLOM_WAJIB = ["kode", "gejala", "diagnosis_pakar"]
SUMBER_LITERATUR = os.path.splitext(os.path.basename(KASUS_LITERATUR))[0]
PENANDA_CONTOH = "CONTOH_HAPUS"   # baris contoh dari spesifikasi A3, tidak ikut dihitung


def urai_gejala(teks):
    """Ubah teks gejala menjadi dict masukan diagnosis.

    Format yang diterima:
        "G01=0.8; G02=0.6"   (pemisah titik koma)
        "G01=0,8; G02=0,6"   (desimal koma, gaya Indonesia)
        "G01=0.8, G02=0.6"   (pemisah koma, asalkan diikuti kode G)

    Mengembalikan:
        {"G01": 0.8, "G02": 0.6}. Teks kosong -> {}.

    Error:
        ValueError kalau ada bagian yang nilainya bukan angka.
    """
    hasil = {}
    for bagian in re.split(r";|,(?=\s*[Gg]\d)", teks or ""):
        bagian = bagian.strip()
        if not bagian:
            continue
        kode, _, nilai = bagian.partition("=")
        try:
            hasil[kode.strip().upper()] = float(nilai.strip().replace(",", "."))
        except ValueError:
            raise ValueError(f"Format gejala salah: '{bagian}' (contoh benar: G01=0.8)") from None
    return hasil


def baca_kasus(path):
    """Baca satu file kasus. Setiap baris diberi kunci "_sumber" (nama file tanpa ekstensi).

    Baris tanpa kode diabaikan (misalnya baris kosong dari sheet).

    Error:
        ValueError kalau kolom wajib tidak ada.
    """
    sumber = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8-sig", newline="") as f:
        baris = list(csv.DictReader(f))
    hilang = [k for k in KOLOM_WAJIB if baris and k not in baris[0]]
    if hilang:
        raise ValueError(f"{path}: kolom wajib tidak ada: {', '.join(hilang)}")
    return [{**b, "_sumber": sumber} for b in baris if (b.get("kode") or "").strip()]


def berlabel(kasus):
    """True kalau kasus punya diagnosis rujukan dan bukan baris contoh."""
    rujukan = (kasus.get("diagnosis_pakar") or "").strip()
    return bool(rujukan) and PENANDA_CONTOH not in rujukan and PENANDA_CONTOH not in kasus["kode"]


def diagnosis_teratas(out):
    """Ambil diagnosis sistem dari keluaran diagnosis()/diagnosis_ds().

    Mengembalikan:
        (kode, persen, seri)
        - kode  : "P01", atau "P05/P06/P07" kalau seri, atau "-" kalau tidak ada yang tampil
        - persen: persen penyakit teratas, "" kalau tidak ada
        - seri  : True kalau lebih dari satu penyakit di puncak
    """
    tampil = [h for h in out["hasil"] if h["tampil"]]
    if not tampil:
        return "-", "", False
    puncak = [h["kode"] for h in tampil if h["cf"] == tampil[0]["cf"]]
    return "/".join(puncak), tampil[0]["persen"], len(puncak) > 1


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


if __name__ == "__main__":
    evaluasi(*sys.argv[1:3])
