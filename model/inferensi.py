"""Mesin inferensi: Forward Chaining + Certainty Factor (CF).

Modul ini adalah "otak" sistem pakar. Isinya tiga kelompok fungsi:

1. Basis pengetahuan  : muat_kb, periksa_kb, daftar_pertanyaan
2. Rumus CF           : gabung_cf, rumus_gabung
3. Diagnosis          : periksa_masukan, forward_chaining, susun_hasil, diagnosis

Semua data (gejala, penyakit, aturan, skala CF) dibaca dari basis_pengetahuan.json.
Tidak ada data yang ditulis langsung di kode.

Kontrak untuk tim web (DIBEKUKAN, lihat docs/specification.md bagian 4):

    from inferensi import diagnosis, muat_kb
    kb = muat_kb()
    out = diagnosis({"G01": 0.8, "G02": 0.6}, kb)
    # out = {"hasil", "fakta_antara", "jejak", "aturan_jalan", "waktu_ms"}

Jalankan `python inferensi.py` untuk mode tanya-jawab di terminal.
"""

import json
import os
import time

LOKASI_KB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basis_pengetahuan.json")


# ---------------------------------------------------------------------------
# 1. Basis pengetahuan
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 2. Rumus Certainty Factor
# ---------------------------------------------------------------------------

def angka(x):
    """Format angka untuk teks jejak: maksimal 4 desimal, tanpa nol di belakang (0.8, bukan 0.8000)."""
    s = f"{round(x, 4):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def gabung_cf(cf1, cf2):
    """Gabungkan dua CF untuk kesimpulan yang sama.

    - keduanya >= 0 : CF1 + CF2 x (1 - CF1)
    - keduanya < 0  : CF1 + CF2 x (1 + CF1)
    - beda tanda    : (CF1 + CF2) / (1 - min(|CF1|, |CF2|))
      (kalau +1 dan -1 bertemu, penyebutnya 0: dianggap saling meniadakan, hasil 0)
    """
    if cf1 >= 0 and cf2 >= 0:
        return cf1 + cf2 * (1 - cf1)
    if cf1 < 0 and cf2 < 0:
        return cf1 + cf2 * (1 + cf1)
    penyebut = 1 - min(abs(cf1), abs(cf2))
    return 0.0 if penyebut == 0 else (cf1 + cf2) / penyebut


def rumus_gabung(cf1, cf2, hasil):
    """Tulis rumus gabung_cf() beserta angkanya, untuk ditampilkan di jejak.

    Contoh: rumus_gabung(0.64, 0.36, 0.7696) -> "0.64 + 0.36 x (1 - 0.64) = 0.7696"
    """
    a, b = angka(cf1), angka(cf2)
    if cf1 >= 0 and cf2 >= 0:
        teks = f"{a} + {b} x (1 - {a})"
    elif cf1 < 0 and cf2 < 0:
        teks = f"{a} + ({b}) x (1 + ({a}))"
    else:
        teks = f"({a} + ({b})) / (1 - min(|{a}|, |{b}|))"
    return f"{teks} = {angka(hasil)}"


# ---------------------------------------------------------------------------
# 3. Diagnosis
# ---------------------------------------------------------------------------

def periksa_masukan(input_pengguna, kb):
    """Validasi masukan pengguna dan buang gejala yang dijawab "Tidak tahu" (CF 0).

    Parameter:
        input_pengguna: {kode_gejala: cf_pengguna}, misalnya {"G01": 0.8}. Boleh None.

    Mengembalikan:
        {kode_gejala: cf_pengguna} yang CF-nya > 0.

    Error:
        ValueError kalau kode gejala tidak dikenal atau CF di luar 0..1.
        Rute web sebaiknya menangkap error ini dan membalas status 400.
    """
    fakta = {}
    for kode, cf in (input_pengguna or {}).items():
        if kode not in kb["gejala"]:
            raise ValueError(f"Kode gejala tidak dikenal: {kode}")
        cf = float(cf)
        if not 0 <= cf <= 1:
            raise ValueError(f"CF pengguna untuk {kode} harus di antara 0 dan 1, bukan {cf}")
        if cf > 0:
            fakta[kode] = cf
    return fakta


def teks_fakta_awal(fakta):
    """Baris pertama jejak, misalnya "Fakta awal: G01 (0.8), G02 (0.6)"."""
    if not fakta:
        return "Fakta awal: tidak ada gejala yang dipilih"
    return "Fakta awal: " + ", ".join(f"{k} ({angka(v)})" for k, v in fakta.items())


def cf_aturan(aturan, wm):
    """Hitung CF satu aturan dari CF premis-premisnya di working memory.

    - satu premis : CF premis x CF pakar
    - premis DAN  : min(CF semua premis) x CF pakar

    Mengembalikan:
        (cf_hasil, teks_premis). teks_premis dipakai di jejak, misalnya "0.8" atau "min(0.8, 0.6)".
    """
    nilai = [wm[p] for p in aturan["jika"]]
    if len(nilai) == 1:
        teks = angka(nilai[0])
    else:
        teks = "min(" + ", ".join(angka(v) for v in nilai) + ")"
    return min(nilai) * aturan["cf"], teks


def forward_chaining(fakta_awal, kb):
    """Jalankan forward chaining sampai tidak ada aturan baru yang bisa ditembakkan.

    Cara kerja:
    1. Working memory (wm) diisi gejala dari pengguna.
    2. Setiap putaran, setiap aturan yang belum jalan dicek. Aturan ditembakkan kalau
       semua premisnya ada di wm dengan CF > 0 DAN CF premis itu sudah final
       (penting untuk fakta antara seperti F01: aturan yang memakainya menunggu
       sampai semua aturan yang menghasilkan F01 selesai).
    3. Kesimpulan masuk ke wm. Kalau kesimpulan yang sama sudah ada, CF-nya digabung
       dengan gabung_cf().
    4. Berhenti kalau satu putaran penuh tidak menembakkan aturan apa pun.

    Parameter:
        fakta_awal: {kode_gejala: cf_pengguna}, hasil periksa_masukan().

    Mengembalikan:
        (kesimpulan, aturan_jalan, jejak)
        - kesimpulan  : {kode_penyakit_atau_fakta_antara: cf_akhir}
        - aturan_jalan: kode aturan yang ditembakkan, urut sesuai waktu jalan
        - jejak       : langkah perhitungan dalam bentuk teks
    """
    aturan = kb["aturan"]
    wm = dict(fakta_awal)
    kesimpulan = {}
    aturan_jalan = []
    jejak = []

    def final(kode, dilihat=()):
        """True kalau tidak ada lagi aturan yang masih mungkin mengubah CF `kode`."""
        if kode in kb["gejala"] or kode in dilihat:
            return True
        return not any(
            r["maka"] == kode and r["kode"] not in aturan_jalan and not mati(r, dilihat + (kode,))
            for r in aturan
        )

    def mati(r, dilihat=()):
        """True kalau aturan r tidak akan pernah jalan: ada premis final yang tidak dipercaya."""
        return any(wm.get(p, 0) <= 0 and final(p, dilihat) for p in r["jika"])

    def siap(r):
        """True kalau aturan r boleh ditembakkan sekarang."""
        return (r["kode"] not in aturan_jalan
                and all(wm.get(p, 0) > 0 for p in r["jika"])
                and all(final(p) for p in r["jika"]))

    ada_perubahan = True
    while ada_perubahan:
        ada_perubahan = False
        for r in aturan:
            if not siap(r):
                continue
            ada_perubahan = True
            aturan_jalan.append(r["kode"])

            cf_baru, teks_premis = cf_aturan(r, wm)
            jejak.append(
                f"[{len(aturan_jalan)}] {r['kode']}: JIKA {' DAN '.join(r['jika'])} MAKA {r['maka']} | "
                f"CF = {teks_premis} x {angka(r['cf'])} = {angka(cf_baru)}"
            )

            kode = r["maka"]
            if kode in kesimpulan:
                lama = kesimpulan[kode]
                gabungan = gabung_cf(lama, cf_baru)
                jejak.append(f"    Gabung {kode}: {rumus_gabung(lama, cf_baru, gabungan)}")
                cf_baru = gabungan
            kesimpulan[kode] = cf_baru
            wm[kode] = cf_baru

    return kesimpulan, aturan_jalan, jejak


def susun_hasil(skor, kb):
    """Ubah skor mentah menjadi daftar hasil sesuai kontrak web.

    Dipakai bersama oleh diagnosis() (CF) dan diagnosis_ds() (BetP).

    Parameter:
        skor: {kode_penyakit: nilai}. Nilai boleh negatif (CF).

    Mengembalikan:
        list hasil, urut dari nilai tertinggi (seri diurutkan menurut kode):
        [{"kode", "nama", "cf", "persen", "solusi", "tampil"}, ...]
        "tampil" = True kalau cf >= kb["ambang_tampil"].
    """
    ambang = kb["ambang_tampil"]
    hasil = []
    for kode, nilai in skor.items():
        penyakit = kb["penyakit"][kode]
        cf = round(nilai, 4)
        hasil.append({
            "kode": kode,
            "nama": penyakit["nama"],
            "cf": cf,
            "persen": round(cf * 100, 2),
            "solusi": penyakit["solusi"],
            "tampil": cf >= ambang,
        })
    hasil.sort(key=lambda h: (-h["cf"], h["kode"]))
    return hasil


def buat_keluaran(hasil, fakta_antara, jejak, aturan_jalan, mulai, **tambahan):
    """Bungkus hasil diagnosis menjadi dict sesuai kontrak (dipakai CF dan DS).

    Parameter:
        mulai    : nilai time.perf_counter() saat diagnosis dimulai, untuk menghitung waktu_ms.
        tambahan : kunci opsional, misalnya himpunan_terkuat untuk DS.
    """
    return {
        "hasil": hasil,
        "fakta_antara": fakta_antara,
        "jejak": jejak,
        "aturan_jalan": aturan_jalan,
        "waktu_ms": round((time.perf_counter() - mulai) * 1000, 3),
        **tambahan,
    }


def diagnosis(input_pengguna, kb=None):
    """Diagnosis penyakit dengan Forward Chaining + Certainty Factor.

    Parameter:
        input_pengguna: {kode_gejala: cf_pengguna}, misalnya {"G01": 0.8, "G02": 0.6}.
                        Gejala bernilai 0 ("Tidak tahu") diabaikan.
        kb            : basis pengetahuan dari muat_kb(). Kosong = dibaca dari file.

    Mengembalikan:
        {
          "hasil":        [{"kode", "nama", "cf", "persen", "solusi", "tampil"}, ...],
          "fakta_antara": [{"kode", "nama", "cf", "saran"}, ...],   # misalnya saran periksa akar
          "jejak":        ["Fakta awal: ...", "[1] R01: ...", ...], # fasilitas penjelasan
          "aturan_jalan": ["R01", ...],
          "waktu_ms":     0.05,
        }

    Error:
        ValueError dari periksa_masukan() kalau masukan tidak valid.
    """
    mulai = time.perf_counter()
    kb = kb or muat_kb()
    fakta = periksa_masukan(input_pengguna, kb)

    kesimpulan, aturan_jalan, langkah = forward_chaining(fakta, kb)
    jejak = [teks_fakta_awal(fakta)] + langkah
    if fakta and not aturan_jalan:
        jejak.append("Tidak ada aturan yang terpenuhi")

    hasil = susun_hasil({k: v for k, v in kesimpulan.items() if k in kb["penyakit"]}, kb)
    for h in hasil:
        jejak.append(f"Hasil {h['kode']} {h['nama']}: CF = {angka(h['cf'])} ({h['persen']}%)")

    fakta_antara = [
        {"kode": k, "nama": kb["fakta_antara"][k]["nama"], "cf": round(cf, 4),
         "saran": kb["fakta_antara"][k]["saran"]}
        for k, cf in kesimpulan.items()
        if k in kb.get("fakta_antara", {}) and cf > 0
    ]
    return buat_keluaran(hasil, fakta_antara, jejak, aturan_jalan, mulai)


if __name__ == "__main__":
    from terminal import tanya_jawab

    tanya_jawab(diagnosis)
