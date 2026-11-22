"""Evaluasi akurasi Certainty Factor dan Dempster-Shafer terhadap diagnosis pakar.

Masukan : data/kasus_uji.csv (kolom kode,gejala,diagnosis_pakar), diisi bersama pakar.
Keluaran: data/hasil_evaluasi.csv, kolomnya sama dengan sheet Hasil Evaluasi + kolom Metode.

    python evaluasi.py [path_kasus_uji.csv] [path_hasil.csv]
"""

import csv
import re
import os
import sys

from dempster_shafer import diagnosis_ds
from inferensi import diagnosis, muat_kb

FOLDER = os.path.dirname(os.path.abspath(__file__))
KASUS_UJI = os.path.join(FOLDER, "data", "kasus_uji.csv")
HASIL = os.path.join(FOLDER, "data", "hasil_evaluasi.csv")
PENANDA_CONTOH = "CONTOH_HAPUS"

METODE = [("CF", diagnosis), ("DS", diagnosis_ds)]
KOLOM = ["Kode kasus", "Diagnosis pakar", "Diagnosis sistem (kode)", "CF sistem (%)",
         "Cocok?", "Waktu respons (ms)", "Metode"]


def urai_gejala(teks):
    """'G01=0.8; G02=0.6' -> {'G01': 0.8, 'G02': 0.6}

    Pemisah antargejala ';' (atau ',' sebelum kode G), jadi desimal koma '0,8' tetap bisa.
    """
    hasil = {}
    for bagian in re.split(r";|,(?=\s*[Gg]\d)", teks):
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
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def berlabel(baris):
    pakar = (baris.get("diagnosis_pakar") or "").strip()
    return bool(pakar) and PENANDA_CONTOH not in pakar and PENANDA_CONTOH not in baris["kode"]


def evaluasi(path_kasus=KASUS_UJI, path_hasil=HASIL):
    kb = muat_kb()
    kasus = baca_kasus(path_kasus)
    baris_hasil = []
    ringkasan = {}

    for nama, fungsi in METODE:
        benar = dilabel = 0
        total_ms = 0.0
        for k in kasus:
            out = fungsi(urai_gejala(k["gejala"]), kb)
            teratas = next((h for h in out["hasil"] if h["tampil"]), None)
            sistem = teratas["kode"] if teratas else "-"
            persen = teratas["persen"] if teratas else ""
            pakar = (k.get("diagnosis_pakar") or "").strip().upper()
            if berlabel(k):
                cocok = sistem == pakar
                dilabel += 1
                benar += cocok
                cocok = "TRUE" if cocok else "FALSE"
            else:
                cocok = ""
            total_ms += out["waktu_ms"]
            baris_hasil.append([k["kode"], pakar, sistem, persen, cocok, out["waktu_ms"], nama])
        ringkasan[nama] = (benar, dilabel, total_ms / len(kasus) if kasus else 0.0)

    os.makedirs(os.path.dirname(path_hasil) or ".", exist_ok=True)
    with open(path_hasil, "w", encoding="utf-8", newline="") as f:
        tulis = csv.writer(f)
        tulis.writerow(KOLOM)
        tulis.writerows(baris_hasil)

    cetak(baris_hasil, ringkasan, kasus, path_hasil)
    return baris_hasil, ringkasan


def cetak(baris_hasil, ringkasan, kasus, path_hasil):
    lebar = [15, 13, 8, 8, 6, 10, 6]
    judul = ["Kasus", "Pakar", "Sistem", "CF (%)", "Cocok", "Waktu ms", "Metode"]
    print("  ".join(j.ljust(w) for j, w in zip(judul, lebar)))
    print("-" * (sum(lebar) + 2 * len(lebar)))
    for b in baris_hasil:
        print("  ".join(str(x).ljust(w) for x, w in zip(b, lebar)))
    print()
    for nama, (benar, dilabel, rata_ms) in ringkasan.items():
        akurasi = f"{benar / dilabel * 100:.2f}% ({benar}/{dilabel})" if dilabel else "belum ada kasus berlabel pakar"
        print(f"{nama}: akurasi {akurasi}, rata-rata waktu {rata_ms:.3f} ms")
    if any(not berlabel(k) for k in kasus):
        print(f"\nPeringatan: ada kasus tanpa label pakar atau bertanda {PENANDA_CONTOH}. "
              "Kasus itu tidak dihitung dalam akurasi. Isi data/kasus_uji.csv dari sheet Kasus Uji.")
    print(f"Hasil ditulis ke {path_hasil}")


if __name__ == "__main__":
    evaluasi(*sys.argv[1:3])
