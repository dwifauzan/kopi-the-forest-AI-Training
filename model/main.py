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
    python main.py lembar [--timpa]                  # buat lembar kasus buta untuk pakar
    python main.py impor-pakar LEMBAR.csv [--awalan BS]  # salin isian pakar ke data/kasus_uji.csv
    python main.py api [--host 127.0.0.1] [--port 5001]  # API JSON untuk frontend (docs/api.md)

Modul ini hanya merangkai fungsi dari folder lain; logikanya ada di:
    sistem_pakar/    basis pengetahuan, CF, DS (yang dipakai web)
    antarmuka/       mode terminal dan API JSON untuk frontend
    persiapan_data/  praproses literatur dan lembar pakar
    evaluasi/        akurasi dan uji black box
    tests/           unit test
"""

import argparse
import os
import sys
import unittest

from antarmuka.api import jalankan_server
from antarmuka.terminal import kumpulkan_jawaban, tampilkan_hasil
from evaluasi.akurasi import evaluasi
from evaluasi.black_box import jalankan_blackbox
from persiapan_data.lembar_pakar import NAMA_LEMBAR, buat_lembar, cetak_impor, cetak_lembar, impor_lembar
from persiapan_data.lokasi import FOLDER_LEMBAR
from persiapan_data.praproses import cetak as cetak_praproses
from persiapan_data.praproses import gejala_tanpa_pola, praproses
from sistem_pakar import METODE, daftar_pertanyaan, muat_kb, periksa_kb, urai_gejala
from sistem_pakar.kontrak import ringkas_hasil

FOLDER = os.path.dirname(os.path.abspath(__file__))
FOLDER_TES = os.path.join(FOLDER, "tests")


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

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
            print(f"{nama:17}: {ringkas_hasil(out)}  ({out['waktu_ms']} ms)")


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
    """Jalankan semua file tests/test_*.py. Mengembalikan True kalau semua lulus."""
    suite = unittest.defaultTestLoader.discover(FOLDER_TES, pattern="test_*.py", top_level_dir=FOLDER)
    return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


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


def jalankan_lembar(timpa=False):
    """Buat lembar kasus buta untuk pakar. Mengembalikan False kalau lembar terisi menolak ditimpa."""
    try:
        cetak_lembar(buat_lembar(timpa=timpa))
    except FileExistsError as e:
        print(e)
        return False


def jalankan_impor(path=None, awalan=None):
    """Impor lembar yang sudah diisi pakar ke data/kasus_uji.csv. Mengembalikan False kalau gagal.

    awalan: awalan kode kasus untuk pakar ini; kosong = dari nama pakar di lembar.
    """
    path = path or os.path.join(FOLDER_LEMBAR, NAMA_LEMBAR)
    if not os.path.exists(path):
        print(f"Impor gagal: file tidak ditemukan: {path}. Jalankan 'python main.py lembar' dulu "
              "atau sebutkan lokasi lembar yang sudah diisi pakar.")
        return False
    try:
        cetak_impor(*impor_lembar(path, awalan=awalan))
    except (OSError, ValueError) as e:
        print(f"Impor gagal: {e}")
        return False


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
    ("Buat lembar kasus buta untuk pakar", jalankan_lembar),
    ("Impor hasil isian pakar", jalankan_impor),
    ("Jalankan API untuk frontend", jalankan_server),
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
    p = sub.add_parser("lembar", help="buat lembar kasus buta untuk pakar")
    p.add_argument("--timpa", action="store_true", help="buat ulang walau lembar sudah mulai diisi")
    p = sub.add_parser("impor-pakar", help="salin hasil isian pakar ke data/kasus_uji.csv")
    p.add_argument("lembar", nargs="?", help="bawaan: data/lembar_pakar/lembar_pakar.csv")
    p.add_argument("--awalan", help="awalan kode kasus pakar ini, misalnya BS (bawaan: inisial nama pakar)")
    p = sub.add_parser("api", help="jalankan API JSON untuk frontend (docs/api.md)")
    p.add_argument("--host", default="127.0.0.1", help="0.0.0.0 supaya bisa diakses dari perangkat lain")
    p.add_argument("--port", type=int, default=5001)
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
        "lembar": lambda: jalankan_lembar(args.timpa),
        "impor-pakar": lambda: jalankan_impor(args.lembar, args.awalan),
        "api": lambda: jalankan_server(args.host, args.port),
    }.get(args.perintah, menu)
    return 1 if perintah() is False else 0


if __name__ == "__main__":
    sys.exit(main())
