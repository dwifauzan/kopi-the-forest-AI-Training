"""Basis pengetahuan: membaca basis_pengetahuan.json dan memeriksa isinya.

Semua data (gejala, penyakit, aturan, skala CF) hanya ada di basis_pengetahuan.json
(folder model/). Tidak ada data yang ditulis langsung di kode.
"""

import json
import os

LOKASI_KB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "basis_pengetahuan.json")


def muat_kb(path=None):
    """Baca basis pengetahuan dari file JSON.

    Parameter:
        path: lokasi file. Kosong = basis_pengetahuan.json di folder ini.

    Mengembalikan:
        dict dengan kunci "penyakit", "gejala", "aturan", "fakta_antara",
        "skala_cf_pengguna", "ambang_tampil", dan "urutan_bagian".
    """
    with open(path or LOKASI_KB, encoding="utf-8") as f:
        return json.load(f)


def gejala_dipakai(kb):
    """Kode gejala yang muncul sebagai premis di minimal satu aturan."""
    return {p for r in kb["aturan"] for p in r["jika"]}


def daftar_pertanyaan(kb):
    """Susun daftar pertanyaan gejala, dikelompokkan per bagian tanaman.

    Pertanyaan selalu dibentuk dari isi basis pengetahuan, jadi otomatis ikut berubah
    kalau datanya berubah:
    - hanya gejala yang dipakai aturan yang ditanyakan;
    - urutan bagian mengikuti kb["urutan_bagian"]; bagian baru yang belum terdaftar
      tetap ditanyakan, di urutan akhir.

    Dipakai mode terminal, dan bisa dipakai web untuk menyusun form.

    Mengembalikan:
        [(bagian, [(kode_gejala, nama_gejala), ...]), ...]
        contoh: [("Daun", [("G01", "Daun timbul bercak kuning..."), ...]), ...]
    """
    dipakai = gejala_dipakai(kb)
    gejala = [(k, g) for k, g in kb["gejala"].items() if k in dipakai]
    urutan = list(kb.get("urutan_bagian") or [])
    urutan += sorted({g["bagian"] for _, g in gejala} - set(urutan))

    hasil = []
    for bagian in urutan:
        daftar = [(k, g["nama"]) for k, g in gejala if g["bagian"] == bagian]
        if daftar:
            hasil.append((bagian, daftar))
    return hasil


def periksa_kb(kb):
    """Cari ketidaksesuaian di basis pengetahuan.

    Jalankan setiap kali basis_pengetahuan.json diubah (lewat `python main.py cek`).
    Yang diperiksa: kode aturan ganda, aturan yang merujuk kode tidak dikenal, CF pakar
    di luar -1..1, gejala tanpa nama/bagian, gejala yang tidak dipakai aturan, penyakit
    tanpa aturan, bagian yang belum ada di urutan_bagian, dan skala tanpa pilihan 0.

    Mengembalikan:
        daftar pesan masalah (list of str). List kosong = basis pengetahuan aman.
    """
    masalah = []
    dikenal = set(kb["gejala"]) | set(kb["penyakit"]) | set(kb.get("fakta_antara", {}))

    kode_aturan = [r["kode"] for r in kb["aturan"]]
    for kode in sorted({k for k in kode_aturan if kode_aturan.count(k) > 1}):
        masalah.append(f"Kode aturan {kode} dipakai lebih dari sekali")

    for r in kb["aturan"]:
        for p in r["jika"] + [r["maka"]]:
            if p not in dikenal:
                masalah.append(f"{r['kode']}: kode {p} tidak ada di gejala, penyakit, atau fakta antara")
        if not -1 <= r["cf"] <= 1:
            masalah.append(f"{r['kode']}: CF pakar {r['cf']} di luar -1..1")

    dipakai = gejala_dipakai(kb)
    for k, g in kb["gejala"].items():
        if not g.get("nama") or not g.get("bagian"):
            masalah.append(f"{k}: nama atau bagian kosong")
        if k not in dipakai:
            masalah.append(f"{k}: tidak dipakai aturan mana pun, jadi tidak ditanyakan")

    disimpulkan = {r["maka"] for r in kb["aturan"]}
    for k in kb["penyakit"]:
        if k not in disimpulkan:
            masalah.append(f"{k}: tidak ada aturan yang menyimpulkan penyakit ini")

    terdaftar = set(kb.get("urutan_bagian") or [])
    for b in sorted({g["bagian"] for g in kb["gejala"].values()} - terdaftar):
        masalah.append(f"Bagian '{b}' belum ada di urutan_bagian (tetap ditanyakan, di akhir)")

    if not any(s["nilai"] == 0 for s in kb["skala_cf_pengguna"]):
        masalah.append("Skala CF pengguna tidak punya pilihan bernilai 0 (Tidak tahu)")
    return masalah
