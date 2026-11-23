"""Sistem pakar diagnosis penyakit tanaman kopi: basis pengetahuan dan mesin inferensi.

Paket ini satu-satunya yang perlu dipakai web. Kontrak (DIBEKUKAN, docs/specification.md bagian 4):

    from sistem_pakar import diagnosis, diagnosis_ds, muat_kb, daftar_pertanyaan
    kb = muat_kb()
    out = diagnosis({"G01": 0.8, "G02": 0.6}, kb)       # Certainty Factor
    out = diagnosis_ds({"G01": 0.8, "G02": 0.6}, kb)    # Dempster-Shafer, bentuk keluaran sama
    # out = {"hasil", "fakta_antara", "jejak", "aturan_jalan", "waktu_ms"}

    fungsi = METODE["ds"][1]                             # pilih metode dari teks "cf"/"ds"

Isi paket:
    basis_pengetahuan.py : muat dan periksa basis_pengetahuan.json, susun daftar pertanyaan
    kontrak.py           : validasi masukan dan bentuk keluaran yang sama untuk semua metode
    inferensi.py         : Forward Chaining + Certainty Factor
    dempster_shafer.py   : Dempster-Shafer sebagai pembanding

Paket ini tidak mengimpor apa pun dari folder lain dan tidak berisi print/input.
"""

from .basis_pengetahuan import daftar_pertanyaan, muat_kb, periksa_kb
from .dempster_shafer import diagnosis_ds
from .inferensi import diagnosis
from .kontrak import urai_gejala

# Metode yang tersedia: kode -> (nama untuk tampilan, fungsi diagnosis)
METODE = {"cf": ("Certainty Factor", diagnosis), "ds": ("Dempster-Shafer", diagnosis_ds)}

__all__ = ["METODE", "daftar_pertanyaan", "diagnosis", "diagnosis_ds", "muat_kb", "periksa_kb", "urai_gejala"]
