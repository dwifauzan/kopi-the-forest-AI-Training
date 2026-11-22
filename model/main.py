"""Pintu masuk tunggal untuk semua fitur sistem pakar penyakit tanaman kopi.

    python main.py                                   # menu interaktif
    python main.py diagnosis [--metode cf|ds]        # tanya-jawab gejala
    python main.py diagnosis --gejala "G01=0.8; G02=0.6" [--metode cf|ds|keduanya]
    python main.py bandingkan                        # tanya-jawab, hasil CF dan DS berdampingan
    python main.py tes                               # unit test
    python main.py blackbox                          # skenario uji black box dari spesifikasi
    python main.py praproses                         # data mentah -> data/bersih/kasus_literatur.csv
    python main.py evaluasi                          # akurasi terhadap kasus pakar + kasus literatur
    python main.py kb                                # lihat isi basis pengetahuan
    python main.py cek                               # periksa kesesuaian basis pengetahuan dan pemetaan
"""

import argparse
import os
import sys
import unittest

from dempster_shafer import diagnosis_ds
from evaluasi import diagnosis_teratas, evaluasi, urai_gejala
from inferensi import daftar_pertanyaan, diagnosis, kumpulkan_jawaban, muat_kb, periksa_kb, tampilkan_hasil
from praproses import cetak as cetak_praproses
from praproses import praproses

FOLDER = os.path.dirname(os.path.abspath(__file__))
METODE = {"cf": ("Certainty Factor", diagnosis), "ds": ("Dempster-Shafer", diagnosis_ds)}

# Skenario docs/specification.md bagian B5: (nama, masukan, diagnosis teratas yang diharapkan
# ("-" = tidak ada yang tampil, "P05/P06/P07" = seri), persen yang diharapkan untuk CF,
# harus ada saran fakta antara untuk CF)
SKENARIO = [
    ("Semua gejala 'Tidak tahu'", {}, "-", None, False),
    ("Satu gejala (G01 hampir pasti)", {"G01": 0.8}, "P01", 64.0, False),
    ("Karat daun G01=0,8 G02=0,6 G03=0,4", {"G01": 0.8, "G02": 0.6, "G03": 0.4}, "P01", 80.65, False),
    ("CF negatif: G04 pasti, G05 hampir pasti", {"G04": 1.0, "G05": 0.8}, "P02", 70.59, False),
    ("Hanya G08", {"G08": 1.0}, "-", None, False),
    ("G12 + G13 (saran periksa akar)", {"G12": 0.8, "G13": 0.8}, "P05/P06/P07", None, True),
    ("G12 + G13 + G16 (jamur akar putih)", {"G12": 0.8, "G13": 0.8, "G16": 0.8}, "P07", None, True),
]


def ringkas(out):
    tampil = [f"{h['kode']} {h['persen']}%" for h in out["hasil"] if h["tampil"]][:3]
    return ", ".join(tampil) or "tidak ada yang tampil"


def jalankan_diagnosis(metode="cf", gejala=None):
    kb = muat_kb()
    try:
        jawaban = urai_gejala(gejala) if gejala else kumpulkan_jawaban(kb)
        jawaban = {k: v for k, v in jawaban.items() if v > 0}
        if not jawaban:
            print("\nSemua gejala 'Tidak tahu'. Pilih minimal satu gejala.")
            return
        if metode == "keduanya":
            bandingkan_hasil(jawaban, kb)
            return
        nama, fungsi = METODE[metode]
        tampilkan_hasil(fungsi(jawaban, kb), f"Hasil diagnosis ({nama})")
    except ValueError as e:
        print(f"Masukan tidak valid: {e}")


def bandingkan_hasil(jawaban, kb):
    hasil = {nama: fungsi(jawaban, kb) for nama, fungsi in METODE.values()}
    for nama, out in hasil.items():
        tampilkan_hasil(out, f"Hasil diagnosis ({nama})")
    print("\n=== Perbandingan ===")
    for nama, out in hasil.items():
        print(f"{nama:17}: {ringkas(out)}  ({out['waktu_ms']} ms)")


def jalankan_tes():
    suite = unittest.defaultTestLoader.discover(FOLDER, pattern="test_*.py")
    hasil = unittest.TextTestRunner(verbosity=2).run(suite)
    return hasil.wasSuccessful()


def jalankan_blackbox():
    kb = muat_kb()
    lulus_semua = True
    print(f"{'Skenario':42} {'Metode':6} {'Hasil':48} Status")
    print("-" * 106)
    for nama, masukan, kode, persen, saran in SKENARIO:
        asing = [g for g in masukan if g not in kb["gejala"]]
        if asing:
            # basis pengetahuan berubah: skenario ini tidak lagi berlaku
            print(f"{nama:42} {'-':6} {'gejala ' + ', '.join(asing) + ' tidak ada di KB':48} LEWAT")
            continue
        for metode, (_, fungsi) in METODE.items():
            out = fungsi(masukan, kb)
            sistem, persen_sistem, _ = diagnosis_teratas(out)
            ok = sistem == kode
            # angka persen dari spesifikasi hanya berlaku untuk CF; saran F01 hanya ada di CF
            if metode == "cf":
                ok = ok and (persen is None or persen_sistem == persen)
                ok = ok and bool(out["fakta_antara"]) == saran
            lulus_semua &= ok
            teks = ringkas(out) + (" + saran F01" if out["fakta_antara"] else "")
            print(f"{nama:42} {metode.upper():6} {teks[:48]:48} {'LULUS' if ok else 'GAGAL'}")
    print("\nSemua skenario lulus." if lulus_semua else "\nAda skenario yang GAGAL.")
    return lulus_semua


def jalankan_praproses(*path):
    hasil, ditolak = praproses(*path)
    cetak_praproses(hasil, ditolak, *path[1:2])


def cek_data():
    """Periksa basis pengetahuan dan tabel pemetaan. True kalau tidak ada masalah."""
    from praproses import gejala_tanpa_pola, muat_pemetaan

    kb = muat_kb()
    masalah = periksa_kb(kb)
    try:
        belum = gejala_tanpa_pola(kb, muat_pemetaan(kb)[1])
        masalah += [f"{k}: belum punya pola di pemetaan/gejala.csv" for k in belum]
    except (OSError, ValueError) as e:
        masalah.append(f"Pemetaan: {e}")
    jumlah = sum(len(d) for _, d in daftar_pertanyaan(kb))
    print(f"Basis pengetahuan: {len(kb['penyakit'])} penyakit, {len(kb['gejala'])} gejala, "
          f"{len(kb['aturan'])} aturan; {jumlah} gejala ditanyakan")
    for bagian, daftar in daftar_pertanyaan(kb):
        print(f"  {bagian}: {', '.join(k for k, _ in daftar)}")
    if masalah:
        print("\nMasalah:")
        for m in masalah:
            print(f"  - {m}")
    else:
        print("\nTidak ada masalah.")
    return not masalah


def lihat_kb():
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


def menu():
    pilihan = {
        "1": ("Diagnosis (Certainty Factor)", lambda: jalankan_diagnosis("cf")),
        "2": ("Diagnosis (Dempster-Shafer)", lambda: jalankan_diagnosis("ds")),
        "3": ("Bandingkan CF dan DS", lambda: jalankan_diagnosis("keduanya")),
        "4": ("Diagnosis cepat (ketik kode gejala)", diagnosis_cepat),
        "5": ("Jalankan unit test", jalankan_tes),
        "6": ("Uji black box", jalankan_blackbox),
        "7": ("Praproses data mentah", jalankan_praproses),
        "8": ("Evaluasi akurasi", evaluasi),
        "9": ("Lihat basis pengetahuan", lihat_kb),
        "10": ("Periksa kesesuaian data", cek_data),
    }
    while True:
        print("\n=== Sistem Pakar Diagnosis Penyakit Tanaman Kopi ===")
        for k, (nama, _) in pilihan.items():
            print(f"  {k}. {nama}")
        print("  0. Keluar")
        try:
            isi = input("Pilih menu: ").strip()
        except EOFError:
            return
        if isi == "0":
            return
        if isi in pilihan:
            print()
            pilihan[isi][1]()
        else:
            print("Pilihan tidak dikenal.")


def diagnosis_cepat():
    gejala = input("Gejala (contoh: G01=0.8; G02=0.6): ").strip()
    metode = input("Metode cf / ds / keduanya [keduanya]: ").strip().lower() or "keduanya"
    if metode not in ("cf", "ds", "keduanya"):
        print("Metode tidak dikenal.")
        return
    jalankan_diagnosis(metode, gejala)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sistem pakar diagnosis penyakit tanaman kopi")
    sub = parser.add_subparsers(dest="perintah")
    p = sub.add_parser("diagnosis", help="diagnosis gejala")
    p.add_argument("--metode", choices=["cf", "ds", "keduanya"], default="cf")
    p.add_argument("--gejala", help='contoh: "G01=0.8; G02=0.6" (tanpa ini: tanya-jawab)')
    sub.add_parser("bandingkan", help="tanya-jawab, hasil CF dan DS berdampingan")
    sub.add_parser("tes", help="jalankan unit test")
    sub.add_parser("blackbox", help="skenario uji black box")
    p = sub.add_parser("praproses", help="saring data mentah menjadi kasus uji")
    p.add_argument("mentah", nargs="?", help="path CSV data mentah")
    p.add_argument("bersih", nargs="?", help="path CSV hasil")
    p = sub.add_parser("evaluasi", help="akurasi terhadap kasus uji")
    p.add_argument("kasus", nargs="?", help="path satu file kasus (bawaan: kasus pakar + kasus literatur)")
    p.add_argument("hasil", nargs="?", help="path hasil_evaluasi.csv")
    sub.add_parser("kb", help="lihat isi basis pengetahuan")
    sub.add_parser("cek", help="periksa kesesuaian basis pengetahuan dan pemetaan")
    args = parser.parse_args(argv)

    if args.perintah == "diagnosis":
        jalankan_diagnosis(args.metode, args.gejala)
    elif args.perintah == "bandingkan":
        jalankan_diagnosis("keduanya")
    elif args.perintah == "tes":
        return 0 if jalankan_tes() else 1
    elif args.perintah == "blackbox":
        return 0 if jalankan_blackbox() else 1
    elif args.perintah == "praproses":
        jalankan_praproses(*[x for x in (args.mentah, args.bersih) if x])
    elif args.perintah == "evaluasi":
        evaluasi(*[x for x in (args.kasus, args.hasil) if x])
    elif args.perintah == "kb":
        lihat_kb()
    elif args.perintah == "cek":
        return 0 if cek_data() else 1
    else:
        menu()
    return 0


if __name__ == "__main__":
    sys.exit(main())
