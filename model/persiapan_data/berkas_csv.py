"""Baca dan tulis file CSV.

Semua file data dibaca lewat modul ini supaya file dari Excel (BOM, pemisah ";")
dan Google Sheets terbaca sama.
"""

import csv
import json
import os


def pemisah_csv(path):
    """Tebak pemisah kolom dari baris header: ";" (Excel berbahasa Indonesia) atau "," (lainnya)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        header = f.readline()
    return ";" if header.count(";") > header.count(",") else ","


def kolom_csv(path):
    """Nama kolom (header) file CSV. File kosong -> []."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f, delimiter=pemisah_csv(path)), [])


def baca_csv(path):
    """Baca CSV menjadi list of dict (header = kunci).

    Aman untuk file dari Excel: BOM dibuang, dan pemisah ";" dikenali otomatis.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=pemisah_csv(path)))


def tulis_csv(path, kolom, baris):
    """Tulis list of dict ke CSV dengan urutan kolom `kolom`. Folder dibuat kalau belum ada."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        tulis = csv.DictWriter(f, fieldnames=kolom)
        tulis.writeheader()
        tulis.writerows(baris)


def jsonl_ke_csv(path_jsonl, path_csv):
    """Ubah data mentah JSONL (satu objek JSON per baris) menjadi CSV mentah, isinya tidak diubah.

    Semua kunci yang muncul di baris mana pun menjadi kolom; nilai null ditulis kosong.

    Mengembalikan:
        jumlah baris yang ditulis.
    """
    with open(path_jsonl, encoding="utf-8") as f:
        baris = [json.loads(l) for l in f if l.strip()]
    kolom = []
    for b in baris:
        kolom += [k for k in b if k not in kolom]
    tulis_csv(path_csv, kolom, [{k: "" if b.get(k) is None else b[k] for k in kolom} for b in baris])
    return len(baris)
