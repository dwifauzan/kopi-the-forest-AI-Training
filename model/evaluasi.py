"""Evaluasi akurasi Certainty Factor dan Dempster-Shafer terhadap diagnosis pakar.

Masukan : data/kasus_uji.csv (kasus dari pakar) dan data/bersih/kasus_literatur.csv
          (hasil praproses.py), kolom wajib kode,gejala,diagnosis_pakar.
Keluaran: data/hasil_evaluasi.csv, kolomnya sama dengan sheet Hasil Evaluasi + kolom Metode
          dan Sumber data. Akurasi dilaporkan terpisah per sumber.

    python evaluasi.py [path_kasus.csv] [path_hasil.csv]
"""

import csv
import re
import os
import sys

from dempster_shafer import diagnosis_ds
from inferensi import diagnosis, muat_kb

FOLDER = os.path.dirname(os.path.abspath(__file__))
KASUS_UJI = os.path.join(FOLDER, "data", "kasus_uji.csv")
KASUS_LITERATUR = os.path.join(FOLDER, "data", "bersih", "kasus_literatur.csv")
SUMBER_KASUS = [KASUS_UJI, KASUS_LITERATUR]
HASIL = os.path.join(FOLDER, "data", "hasil_evaluasi.csv")
PENANDA_CONTOH = "CONTOH_HAPUS"

METODE = [("CF", diagnosis), ("DS", diagnosis_ds)]
KOLOM = ["Kode kasus", "Diagnosis pakar", "Diagnosis sistem (kode)", "CF sistem (%)",
         "Cocok?", "Waktu respons (ms)", "Metode", "Sumber data"]
KOLOM_WAJIB = ["kode", "gejala", "diagnosis_pakar"]
JENIS_LITERATUR = os.path.splitext(os.path.basename(KASUS_LITERATUR))[0]


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
    """Baca file kasus. Setiap baris diberi '_sumber' (nama file tanpa ekstensi)."""
    sumber = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8-sig", newline="") as f:
        baris = list(csv.DictReader(f))
    hilang = [k for k in KOLOM_WAJIB if baris and k not in baris[0]]
    if hilang:
        raise ValueError(f"{path}: kolom wajib tidak ada: {', '.join(hilang)}")
    return [{**b, "_sumber": sumber} for b in baris if (b.get("kode") or "").strip()]


def berlabel(baris):
    pakar = (baris.get("diagnosis_pakar") or "").strip()
    return bool(pakar) and PENANDA_CONTOH not in pakar and PENANDA_CONTOH not in baris["kode"]


def diagnosis_teratas(out):
    """Kode penyakit teratas yang tampil. Kalau beberapa penyakit seri, digabung 'P05/P06/P07'."""
    tampil = [h for h in out["hasil"] if h["tampil"]]
    if not tampil:
        return "-", "", False
    seri = [h["kode"] for h in tampil if h["cf"] == tampil[0]["cf"]]
    return "/".join(seri), tampil[0]["persen"], len(seri) > 1


def periksa_kasus(kasus, kb):
    """Peringatan untuk kode kasus ganda dan diagnosis pakar yang tidak dikenal."""
    peringatan = []
    dilihat = set()
    for k in kasus:
        if k["kode"] in dilihat:
            peringatan.append(f"Kode kasus {k['kode']} muncul lebih dari sekali")
        dilihat.add(k["kode"])
        pakar = (k.get("diagnosis_pakar") or "").strip().upper()
        if berlabel(k) and pakar != "-" and pakar not in kb["penyakit"]:
            peringatan.append(f"{k['kode']}: diagnosis pakar '{pakar}' tidak ada di basis pengetahuan, pasti tidak cocok")
    return peringatan


def evaluasi(path_kasus=None, path_hasil=HASIL):
    """path_kasus: satu path, daftar path, atau None (semua SUMBER_KASUS yang ada)."""
    kb = muat_kb()
    if path_kasus is None:
        path_kasus = [p for p in SUMBER_KASUS if os.path.exists(p)]
    elif isinstance(path_kasus, str):
        path_kasus = [path_kasus]
    kasus = [k for p in path_kasus for k in baca_kasus(p)]
    peringatan = periksa_kasus(kasus, kb)

    masukan = {}
    for k in kasus:
        try:
            masukan[k["kode"]] = urai_gejala(k["gejala"] or "")
        except ValueError as e:
            raise ValueError(f"Kasus {k['kode']} ({k['_sumber']}): {e}") from None

    baris_hasil = []
    ringkasan = {}   # (metode, sumber) -> [benar, dilabel, seri, total_ms, jumlah]

    for nama, fungsi in METODE:
        for k in kasus:
            out = fungsi(masukan[k["kode"]], kb)
            sistem, persen, seri = diagnosis_teratas(out)
            pakar = (k.get("diagnosis_pakar") or "").strip().upper()
            r = ringkasan.setdefault((nama, k["_sumber"]), [0, 0, 0, 0.0, 0])
            if berlabel(k):
                cocok = sistem == pakar
                r[0] += cocok
                r[1] += 1
                r[2] += seri
                cocok = "TRUE" if cocok else "FALSE"
            else:
                cocok = ""
            r[3] += out["waktu_ms"]
            r[4] += 1
            baris_hasil.append([k["kode"], pakar, sistem, persen, cocok, out["waktu_ms"], nama, k["_sumber"]])

    os.makedirs(os.path.dirname(path_hasil) or ".", exist_ok=True)
    with open(path_hasil, "w", encoding="utf-8", newline="") as f:
        tulis = csv.writer(f)
        tulis.writerow(KOLOM)
        tulis.writerows(baris_hasil)

    cetak(baris_hasil, ringkasan, kasus, path_hasil, peringatan)
    return baris_hasil, ringkasan


def cetak(baris_hasil, ringkasan, kasus, path_hasil, peringatan=()):
    lebar = [15, 13, 12, 8, 6, 10, 6, 16]
    judul = ["Kasus", "Pakar", "Sistem", "CF (%)", "Cocok", "Waktu ms", "Metode", "Sumber"]
    print("  ".join(j.ljust(w) for j, w in zip(judul, lebar)))
    print("-" * (sum(lebar) + 2 * len(lebar)))
    for b in baris_hasil:
        print("  ".join(str(x).ljust(w) for x, w in zip(b, lebar)))
    print()
    for (nama, sumber), (benar, dilabel, seri, total_ms, jumlah) in ringkasan.items():
        jenis = "kesesuaian literatur" if sumber == JENIS_LITERATUR else "akurasi"
        if dilabel:
            nilai = f"{benar / dilabel * 100:.2f}% ({benar}/{dilabel})"
            if seri:
                nilai += f", {seri} kasus seri dihitung tidak cocok"
        else:
            nilai = "belum ada kasus berlabel"
        print(f"{nama} [{sumber}]: {jenis} {nilai}, rata-rata waktu {total_ms / jumlah:.3f} ms")
    for p in peringatan:
        print(f"Peringatan: {p}")
    if any(not berlabel(k) for k in kasus):
        print("Peringatan: ada kasus tanpa label pakar. Kasus itu tidak dihitung.")
    if not kasus:
        print("Belum ada kasus. Isi data/kasus_uji.csv dari sheet Kasus Uji atau jalankan praproses.py.")
    print(f"Hasil ditulis ke {path_hasil}")


if __name__ == "__main__":
    evaluasi(*sys.argv[1:3])
