"""Uji black box: skenario dari docs/specification.md bagian B5, dijalankan dengan CF dan DS.

    python main.py blackbox
"""

from sistem_pakar import METODE, muat_kb
from sistem_pakar.kontrak import diagnosis_teratas, ringkas_hasil

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
            teks = ringkas_hasil(out) + (" + saran F01" if out["fakta_antara"] else "")
            print(f"{nama:42} {metode.upper():6} {teks[:48]:48} {'LULUS' if ok else 'GAGAL'}")
    print("\nSemua skenario lulus." if lulus_semua else "\nAda skenario yang GAGAL.")
    return lulus_semua
