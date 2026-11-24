"""Baca dan tulis file CSV.

Semua file data dibaca lewat modul ini supaya file dari Excel (BOM, pemisah ";")
dan Google Sheets terbaca sama.
"""

import csv
import io
import json
import os


def baca_teks(path):
    """Baca isi file sebagai UTF-8 (BOM dari Excel dibuang).

    Error:
        ValueError berbahasa Indonesia kalau file bukan CSV UTF-8, misalnya .xlsx atau
        "CSV (Comma delimited)" lama dari Excel.
    """
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return f.read()
    except UnicodeDecodeError:
        raise ValueError(f"{path}: file bukan CSV UTF-8. Di Excel pilih Save As -> "
                         "'CSV UTF-8 (Comma delimited)'; di Google Sheets pilih Download -> CSV.") from None


def pemisah_csv(teks):
    """Tebak pemisah kolom dari baris header: ";" (Excel berbahasa Indonesia) atau "," (lainnya)."""
    header = teks.split("\n", 1)[0]
    return ";" if header.count(";") > header.count(",") else ","


def kolom_csv(path):
    """Nama kolom (header) file CSV. File kosong -> []."""
    teks = baca_teks(path)
    return next(csv.reader(io.StringIO(teks), delimiter=pemisah_csv(teks)), [])


def baca_csv(path):
    """Baca CSV menjadi list of dict (header = kunci).

    Aman untuk file dari Excel: BOM dibuang, dan pemisah ";" dikenali otomatis.
    """
    teks = baca_teks(path)
    return list(csv.DictReader(io.StringIO(teks), delimiter=pemisah_csv(teks)))


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
