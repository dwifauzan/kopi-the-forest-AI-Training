"""Pintu masuk tunggal untuk semua fitur sistem pakar penyakit tanaman kopi.

    python main.py                                   # menu interaktif
    python main.py diagnosis [--metode cf|ds|keduanya] [--gejala "G01=0.8; G02=0.6"]
    python main.py bandingkan                        # tanya-jawab, hasil CF dan DS berdampingan
    python main.py tes                               # semua unit test
    python main.py blackbox                          # skenario uji black box dari spesifikasi
    python main.py praproses [mentah.csv] [bersih.csv]
    python main.py evaluasi [kasus.csv] [hasil.csv]
    python main.py kb                                # lihat isi basis pengetahuan
    python main.py cek                               # periksa basis pengetahuan dan pemetaan

Modul ini hanya merangkai fungsi dari modul lain; logikanya ada di:
    inferensi.py (CF), dempster_shafer.py (DS), evaluasi.py, praproses.py, terminal.py
"""

import argparse
import os
import sys
import unittest

from dempster_shafer import diagnosis_ds
from evaluasi import diagnosis_teratas, evaluasi, urai_gejala
from inferensi import daftar_pertanyaan, diagnosis, muat_kb, periksa_kb
from praproses import cetak as cetak_praproses
from praproses import gejala_tanpa_pola, praproses
from terminal import kumpulkan_jawaban, tampilkan_hasil

FOLDER = os.path.dirname(os.path.abspath(__file__))
METODE = {"cf": ("Certainty Factor", diagnosis), "ds": ("Dempster-Shafer", diagnosis_ds)}

# Skenario uji black box (docs/specification.md bagian B5). Per baris:
#   (nama, masukan, diagnosis teratas yang diharapkan, persen yang diharapkan untuk CF,
#    apakah CF harus memberi saran fakta antara)
# Diagnosis "-" = tidak ada yang tampil; "P05/P06/P07" = seri.
SKENARIO = [
    ("Semua gejala 'Tidak tahu'", {}, "-", None, False),
    ("Satu gejala (G01 hampir pasti)", {"G01": 0.8}, "P01", 64.0, False),
    ("Karat daun G01=0,8 G02=0,6 G03=0,4", {"G01": 0.8, "G02": 0.6, "G03": 0.4}, "P01", 80.65, False),
    ("CF negatif: G04 pasti, G05 hampir pasti", {"G04": 1.0, "G05": 0.8}, "P02", 70.59, False),
    ("Hanya G08", {"G08": 1.0}, "-", None, False),
    ("G12 + G13 (saran periksa akar)", {"G12": 0.8, "G13": 0.8}, "P05/P06/P07", None, True),
    ("G12 + G13 + G16 (jamur akar putih)", {"G12": 0.8, "G13": 0.8, "G16": 0.8}, "P07", None, True),
]


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

def ringkas(out):
    """Maksimal tiga penyakit teratas yang tampil, misalnya "P01 80.65%, P03 36.0%"."""
    tampil = [f"{h['kode']} {h['persen']}%" for h in out["hasil"] if h["tampil"]][:3]
    return ", ".join(tampil) or "tidak ada yang tampil"


def jalankan_diagnosis(metode="cf", gejala=None):
    """Diagnosis dari terminal.

    Parameter:
        metode: "cf", "ds", atau "keduanya".
        gejala: teks seperti "G01=0.8; G02=0.6". Kosong = tanya-jawab satu per satu.

    Masukan yang tidak valid dilaporkan sebagai pesan, bukan error.
    """
    kb = muat_kb()
    try:
        jawaban = urai_gejala(gejala) if gejala else kumpulkan_jawaban(kb)
        jawaban = {k: v for k, v in jawaban.items() if v > 0}
        if not jawaban:
            print("\nSemua gejala 'Tidak tahu'. Pilih minimal satu gejala.")
            return
        dipilih = METODE.values() if metode == "keduanya" else [METODE[metode]]
        hasil = {nama: fungsi(jawaban, kb) for nama, fungsi in dipilih}
    except ValueError as e:
        print(f"Masukan tidak valid: {e}")
        return

    for nama, out in hasil.items():
        tampilkan_hasil(out, f"Hasil diagnosis ({nama})")
    if len(hasil) > 1:
        print("\n=== Perbandingan ===")
        for nama, out in hasil.items():
            print(f"{nama:17}: {ringkas(out)}  ({out['waktu_ms']} ms)")


def diagnosis_cepat():
    """Menu: ketik kode gejala langsung, lalu pilih metode."""
    gejala = input("Gejala (contoh: G01=0.8; G02=0.6): ").strip()
    metode = input("Metode cf / ds / keduanya [keduanya]: ").strip().lower() or "keduanya"
    if metode not in ("cf", "ds", "keduanya"):
        print("Metode tidak dikenal.")
        return
    jalankan_diagnosis(metode, gejala)


# ---------------------------------------------------------------------------
# Pengujian dan data
# ---------------------------------------------------------------------------

def jalankan_tes():
    """Jalankan semua file test_*.py. Mengembalikan True kalau semua lulus."""
    suite = unittest.defaultTestLoader.discover(FOLDER, pattern="test_*.py")
    return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


def jalankan_blackbox():
    """Jalankan SKENARIO dengan CF dan DS, cetak LULUS/GAGAL. Mengembalikan True kalau semua lulus.

    Angka persen dan saran fakta antara hanya dicek untuk CF, karena angka di spesifikasi
    adalah angka CF. Skenario yang memakai gejala yang sudah tidak ada di basis
    pengetahuan ditandai LEWAT.
    """
    kb = muat_kb()
    lulus_semua = True
    print(f"{'Skenario':42} {'Metode':6} {'Hasil':48} Status")
    print("-" * 106)
    for nama, masukan, harapan, persen, saran in SKENARIO:
        asing = [g for g in masukan if g not in kb["gejala"]]
        if asing:
            print(f"{nama:42} {'-':6} {'gejala ' + ', '.join(asing) + ' tidak ada di KB':48} LEWAT")
            continue
        for metode, (_, fungsi) in METODE.items():
            out = fungsi(masukan, kb)
            sistem, persen_sistem, _ = diagnosis_teratas(out)
            ok = sistem == harapan
            if metode == "cf":
                ok = ok and (persen is None or persen_sistem == persen)
                ok = ok and bool(out["fakta_antara"]) == saran
            lulus_semua &= ok
            teks = ringkas(out) + (" + saran F01" if out["fakta_antara"] else "")
            print(f"{nama:42} {metode.upper():6} {teks[:48]:48} {'LULUS' if ok else 'GAGAL'}")
    print("\nSemua skenario lulus." if lulus_semua else "\nAda skenario yang GAGAL.")
    return lulus_semua


def jalankan_praproses(*path):
    """Praproses data mentah lalu cetak ringkasannya. path = (mentah, bersih), boleh kosong."""
    kasus, ditolak = praproses(*path)
    cetak_praproses(kasus, ditolak, *path[1:2])


def cek_data():
    """Periksa basis pengetahuan (periksa_kb) dan pemetaan gejala. Mengembalikan True kalau aman."""
    kb = muat_kb()
    masalah = periksa_kb(kb)
    try:
        masalah += [f"{k}: belum punya pola di pemetaan/gejala.csv" for k in gejala_tanpa_pola(kb)]
    except (OSError, ValueError) as e:
        masalah.append(f"Pemetaan: {e}")

    pertanyaan = daftar_pertanyaan(kb)
    print(f"Basis pengetahuan: {len(kb['penyakit'])} penyakit, {len(kb['gejala'])} gejala, "
          f"{len(kb['aturan'])} aturan; {sum(len(d) for _, d in pertanyaan)} gejala ditanyakan")
    for bagian, daftar in pertanyaan:
        print(f"  {bagian}: {', '.join(k for k, _ in daftar)}")
    print("\nMasalah:\n" + "\n".join(f"  - {m}" for m in masalah) if masalah else "\nTidak ada masalah.")
    return not masalah


def lihat_kb():
    """Cetak isi basis pengetahuan: penyakit, gejala, aturan, skala CF, dan ambang tampil."""
    kb = muat_kb()
    print(f"=== Penyakit ({len(kb['penyakit'])}) ===")
    for k, p in kb["penyakit"].items():
        print(f"{k}  {p['nama']} ({p['penyebab']})")
    print(f"\n=== Gejala ({len(kb['gejala'])}) ===")
    for k, g in kb["gejala"].items():
        print(f"{k}  [{g['bagian']}] {g['nama']}")
    print(f"\n=== Aturan ({len(kb['aturan'])}) ===")
    for r in kb["aturan"]:
        print(f"{r['kode']}  JIKA {' DAN '.join(r['jika']):10} MAKA {r['maka']}  CF {r['cf']:>4}  ({r['status']})")
    print("\n=== Skala CF pengguna ===")
    for s in kb["skala_cf_pengguna"]:
        print(f"{s['nilai']}  {s['label']}")
    print(f"\nAmbang tampil: {kb['ambang_tampil']}")


# ---------------------------------------------------------------------------
# Menu dan CLI
# ---------------------------------------------------------------------------

MENU = [
    ("Diagnosis (Certainty Factor)", lambda: jalankan_diagnosis("cf")),
    ("Diagnosis (Dempster-Shafer)", lambda: jalankan_diagnosis("ds")),
    ("Bandingkan CF dan DS", lambda: jalankan_diagnosis("keduanya")),
    ("Diagnosis cepat (ketik kode gejala)", diagnosis_cepat),
    ("Jalankan unit test", jalankan_tes),
    ("Uji black box", jalankan_blackbox),
    ("Praproses data mentah", jalankan_praproses),
    ("Evaluasi akurasi", evaluasi),
    ("Lihat basis pengetahuan", lihat_kb),
    ("Periksa kesesuaian data", cek_data),
]


def menu():
    """Menu interaktif. Nomor menu = urutan di MENU, 0 = keluar."""
    while True:
        print("\n=== Sistem Pakar Diagnosis Penyakit Tanaman Kopi ===")
        for i, (nama, _) in enumerate(MENU, 1):
            print(f"  {i}. {nama}")
        print("  0. Keluar")
        try:
            isi = input("Pilih menu: ").strip()
        except EOFError:
            return
        if isi == "0":
            return
        if isi.isdigit() and 1 <= int(isi) <= len(MENU):
            print()
            MENU[int(isi) - 1][1]()
        else:
            print("Pilihan tidak dikenal.")


def buat_parser():
    """Susun argumen baris perintah. Setiap subperintah memanggil satu fungsi di atas."""
    parser = argparse.ArgumentParser(description="Sistem pakar diagnosis penyakit tanaman kopi")
    sub = parser.add_subparsers(dest="perintah")

    p = sub.add_parser("diagnosis", help="diagnosis gejala")
    p.add_argument("--metode", choices=["cf", "ds", "keduanya"], default="cf")
    p.add_argument("--gejala", help='contoh: "G01=0.8; G02=0.6" (tanpa ini: tanya-jawab)')
    sub.add_parser("bandingkan", help="tanya-jawab, hasil CF dan DS berdampingan")
    sub.add_parser("tes", help="jalankan semua unit test")
    sub.add_parser("blackbox", help="skenario uji black box")
    p = sub.add_parser("praproses", help="saring data mentah menjadi kasus uji")
    p.add_argument("path", nargs="*", metavar="PATH", help="[mentah.csv] [bersih.csv]")
    p = sub.add_parser("evaluasi", help="akurasi CF dan DS terhadap kasus uji")
    p.add_argument("path", nargs="*", metavar="PATH",
                   help="[kasus.csv] [hasil.csv]; bawaan: kasus pakar + kasus literatur")
    sub.add_parser("kb", help="lihat isi basis pengetahuan")
    sub.add_parser("cek", help="periksa basis pengetahuan dan pemetaan")
    return parser


def main(argv=None):
    """Jalankan subperintah dari baris perintah, atau menu kalau tidak ada subperintah.

    Mengembalikan:
        kode keluar: 0 = berhasil, 1 = ada tes/skenario/pemeriksaan yang gagal.
    """
    args = buat_parser().parse_args(argv)
    path = getattr(args, "path", [])[:2]
    perintah = {
        "diagnosis": lambda: jalankan_diagnosis(args.metode, args.gejala),
        "bandingkan": lambda: jalankan_diagnosis("keduanya"),
        "tes": jalankan_tes,
        "blackbox": jalankan_blackbox,
        "praproses": lambda: jalankan_praproses(*path),
        "evaluasi": lambda: evaluasi(*path),
        "kb": lihat_kb,
        "cek": cek_data,
    }.get(args.perintah, menu)
    return 1 if perintah() is False else 0


if __name__ == "__main__":
    sys.exit(main())
