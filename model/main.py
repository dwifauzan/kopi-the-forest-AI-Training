"""Pintu masuk tunggal untuk semua fitur sistem pakar penyakit tanaman kopi.

    python main.py                                   # menu interaktif
    python main.py diagnosis [--metode cf|ds]        # tanya-jawab gejala
    python main.py diagnosis --gejala "G01=0.8; G02=0.6" [--metode cf|ds|keduanya]
    python main.py bandingkan                        # tanya-jawab, hasil CF dan DS berdampingan
    python main.py tes                               # unit test
    python main.py blackbox                          # skenario uji black box dari spesifikasi
    python main.py evaluasi                          # akurasi terhadap data/kasus_uji.csv
    python main.py kb                                # lihat isi basis pengetahuan
"""

import argparse
import os
import sys
import unittest

from dempster_shafer import diagnosis_ds
from evaluasi import evaluasi, urai_gejala
from inferensi import diagnosis, kumpulkan_jawaban, muat_kb, tampilkan_hasil

FOLDER = os.path.dirname(os.path.abspath(__file__))
METODE = {"cf": ("Certainty Factor", diagnosis), "ds": ("Dempster-Shafer", diagnosis_ds)}

# Skenario docs/specification.md bagian B5: (nama, masukan, kode teratas yang diharapkan,
# persen yang diharapkan untuk CF, harus ada saran fakta antara)
SKENARIO = [
    ("Semua gejala 'Tidak tahu'", {}, None, None, False),
    ("Satu gejala (G01 hampir pasti)", {"G01": 0.8}, "P01", 64.0, False),
    ("Karat daun G01=0,8 G02=0,6 G03=0,4", {"G01": 0.8, "G02": 0.6, "G03": 0.4}, "P01", 80.65, False),
    ("CF negatif: G04 pasti, G05 hampir pasti", {"G04": 1.0, "G05": 0.8}, "P02", 70.59, False),
    ("Hanya G08", {"G08": 1.0}, None, None, False),
    ("G12 + G13 (saran periksa akar)", {"G12": 0.8, "G13": 0.8}, None, None, True),
    ("G12 + G13 + G16 (jamur akar putih)", {"G12": 0.8, "G13": 0.8, "G16": 0.8}, "P07", None, True),
]


def teratas(out):
    return next((h for h in out["hasil"] if h["tampil"]), None)


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
    for kode in METODE:
        nama, fungsi = METODE[kode]
        tampilkan_hasil(fungsi(jawaban, kb), f"Hasil diagnosis ({nama})")
    print("\n=== Perbandingan ===")
    for kode in METODE:
        nama, fungsi = METODE[kode]
        out = fungsi(jawaban, kb)
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
        for metode, (_, fungsi) in METODE.items():
            out = fungsi(masukan, kb)
            atas = teratas(out)
            ok = (atas["kode"] if atas else None) == kode
            # angka persen dari spesifikasi hanya berlaku untuk CF; saran F01 hanya ada di CF
            if metode == "cf":
                ok = ok and (persen is None or atas["persen"] == persen)
                ok = ok and bool(out["fakta_antara"]) == saran
            if kode is None and masukan.get("G12"):
                # P05/P06/P07 seri: cukup pastikan ketiganya sama
                nilai = {h["cf"] for h in out["hasil"] if h["kode"] in ("P05", "P06", "P07")}
                ok = len(nilai) == 1 and (metode == "ds" or bool(out["fakta_antara"]))
            lulus_semua &= ok
            teks = ringkas(out) + (" + saran F01" if out["fakta_antara"] else "")
            print(f"{nama:42} {metode.upper():6} {teks[:48]:48} {'LULUS' if ok else 'GAGAL'}")
    print("\nSemua skenario lulus." if lulus_semua else "\nAda skenario yang GAGAL.")
    return lulus_semua


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
        "7": ("Evaluasi akurasi", evaluasi),
        "8": ("Lihat basis pengetahuan", lihat_kb),
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
    p = sub.add_parser("evaluasi", help="akurasi terhadap kasus uji")
    p.add_argument("kasus", nargs="?", help="path kasus_uji.csv")
    p.add_argument("hasil", nargs="?", help="path hasil_evaluasi.csv")
    sub.add_parser("kb", help="lihat isi basis pengetahuan")
    args = parser.parse_args(argv)

    if args.perintah == "diagnosis":
        jalankan_diagnosis(args.metode, args.gejala)
    elif args.perintah == "bandingkan":
        jalankan_diagnosis("keduanya")
    elif args.perintah == "tes":
        return 0 if jalankan_tes() else 1
    elif args.perintah == "blackbox":
        return 0 if jalankan_blackbox() else 1
    elif args.perintah == "evaluasi":
        evaluasi(*[x for x in (args.kasus, args.hasil) if x])
    elif args.perintah == "kb":
        lihat_kb()
    else:
        menu()
    return 0


if __name__ == "__main__":
    sys.exit(main())
