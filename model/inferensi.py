"""Mesin inferensi sistem pakar penyakit tanaman kopi.

Metode: Forward Chaining + Certainty Factor, hanya memakai Python standar.
Basis pengetahuan dibaca dari basis_pengetahuan.json (satu-satunya sumber data).

Kontrak (DIBEKUKAN, lihat docs/specification.md bagian 4):
    kb = muat_kb()
    out = diagnosis({"G01": 0.8, "G02": 0.6}, kb)
"""

import json
import os
import time

LOKASI_KB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basis_pengetahuan.json")


def muat_kb(path=None):
    """Baca basis pengetahuan dari file JSON."""
    with open(path or LOKASI_KB, encoding="utf-8") as f:
        return json.load(f)


def angka(x):
    """Format angka untuk jejak: maksimal 4 desimal, tanpa nol di belakang."""
    s = f"{round(x, 4):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def gabung_cf(cf1, cf2):
    """Gabungkan dua CF untuk kesimpulan yang sama."""
    if cf1 >= 0 and cf2 >= 0:
        return cf1 + cf2 * (1 - cf1)
    if cf1 < 0 and cf2 < 0:
        return cf1 + cf2 * (1 + cf1)
    penyebut = 1 - min(abs(cf1), abs(cf2))
    if penyebut == 0:  # +1 dan -1: kontradiksi penuh
        return 0.0
    return (cf1 + cf2) / penyebut


def rumus_gabung(cf1, cf2, hasil):
    """Teks rumus gabungan untuk jejak."""
    a, b = angka(cf1), angka(cf2)
    if cf1 >= 0 and cf2 >= 0:
        teks = f"{a} + {b} x (1 - {a})"
    elif cf1 < 0 and cf2 < 0:
        teks = f"{a} + ({b}) x (1 + ({a}))"
    else:
        teks = f"({a} + ({b})) / (1 - min(|{a}|, |{b}|))"
    return f"{teks} = {angka(hasil)}"


def periksa_masukan(input_pengguna, kb):
    """Ambil gejala dengan CF > 0. Kode tak dikenal atau CF di luar 0..1 ditolak."""
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


def nama_kode(kode, kb):
    for kelompok in ("gejala", "penyakit", "fakta_antara"):
        if kode in kb.get(kelompok, {}):
            return kb[kelompok][kode]["nama"]
    return kode


def forward_chaining(fakta_awal, kb):
    """Jalankan forward chaining.

    Mengembalikan (cf_kesimpulan, aturan_jalan, jejak). cf_kesimpulan berisi
    CF akhir setiap penyakit dan fakta antara yang terbentuk.
    """
    aturan = kb["aturan"]
    wm = dict(fakta_awal)          # working memory: kode -> CF
    kesimpulan = {}                # kode penyakit/fakta antara -> CF terkini
    jalan = set()
    aturan_jalan = []
    jejak = []

    def final(kode, dilihat=()):
        """Fakta final kalau tidak ada lagi aturan yang mungkin mengubah CF-nya."""
        if kode in kb["gejala"]:
            return True
        if kode in dilihat:
            return True
        for r in aturan:
            if r["maka"] == kode and r["kode"] not in jalan and not mati(r, dilihat + (kode,)):
                return False
        return True

    def mati(r, dilihat=()):
        """Aturan mati kalau ada premis final yang tidak dipercaya (tidak ada atau CF <= 0)."""
        return any(wm.get(p, 0) <= 0 and final(p, dilihat) for p in r["jika"])

    langkah = 0
    ada_perubahan = True
    while ada_perubahan:
        ada_perubahan = False
        for r in aturan:
            if r["kode"] in jalan:
                continue
            if not all(wm.get(p, 0) > 0 for p in r["jika"]):
                continue
            if not all(final(p) for p in r["jika"]):
                continue  # tunggu sampai CF fakta antara final

            langkah += 1
            jalan.add(r["kode"])
            aturan_jalan.append(r["kode"])
            ada_perubahan = True

            if len(r["jika"]) == 1:
                cf_premis = wm[r["jika"][0]]
                teks_premis = angka(cf_premis)
            else:
                nilai = [wm[p] for p in r["jika"]]
                cf_premis = min(nilai)
                teks_premis = "min(" + ", ".join(angka(v) for v in nilai) + ")"
            cf_aturan = cf_premis * r["cf"]

            jika = " DAN ".join(r["jika"])
            jejak.append(
                f"[{langkah}] {r['kode']}: JIKA {jika} MAKA {r['maka']} | "
                f"CF = {teks_premis} x {angka(r['cf'])} = {angka(cf_aturan)}"
            )

            kode = r["maka"]
            if kode in kesimpulan:
                lama = kesimpulan[kode]
                baru = gabung_cf(lama, cf_aturan)
                jejak.append(f"    Gabung {kode}: {rumus_gabung(lama, cf_aturan, baru)}")
            else:
                baru = cf_aturan
            kesimpulan[kode] = baru
            wm[kode] = baru

    return kesimpulan, aturan_jalan, jejak


def susun_hasil(skor, kb):
    """Ubah {kode_penyakit: cf} menjadi daftar hasil urut CF tertinggi."""
    ambang = kb["ambang_tampil"]
    hasil = []
    for kode, cf in skor.items():
        p = kb["penyakit"][kode]
        cf = round(cf, 4)
        hasil.append({
            "kode": kode,
            "nama": p["nama"],
            "cf": cf,
            "persen": round(cf * 100, 2),
            "solusi": p["solusi"],
            "tampil": cf >= ambang,
        })
    hasil.sort(key=lambda h: (-h["cf"], h["kode"]))
    return hasil


def diagnosis(input_pengguna, kb=None):
    """Diagnosis dengan Forward Chaining + Certainty Factor.

    input_pengguna: {kode_gejala: cf_pengguna}, misalnya {"G01": 0.8}.
    """
    mulai = time.perf_counter()
    kb = kb or muat_kb()
    fakta = periksa_masukan(input_pengguna, kb)

    if fakta:
        jejak = ["Fakta awal: " + ", ".join(f"{k} ({angka(v)})" for k, v in fakta.items())]
    else:
        jejak = ["Fakta awal: tidak ada gejala yang dipilih"]

    kesimpulan, aturan_jalan, langkah = forward_chaining(fakta, kb)
    jejak += langkah
    if not aturan_jalan and fakta:
        jejak.append("Tidak ada aturan yang terpenuhi")

    skor = {k: v for k, v in kesimpulan.items() if k in kb["penyakit"]}
    hasil = susun_hasil(skor, kb)

    fakta_antara = []
    for kode, cf in kesimpulan.items():
        if kode in kb.get("fakta_antara", {}) and cf > 0:
            f = kb["fakta_antara"][kode]
            fakta_antara.append({"kode": kode, "nama": f["nama"], "cf": round(cf, 4), "saran": f["saran"]})

    for h in hasil:
        jejak.append(f"Hasil {h['kode']} {h['nama']}: CF = {angka(h['cf'])} ({h['persen']}%)")

    return {
        "hasil": hasil,
        "fakta_antara": fakta_antara,
        "jejak": jejak,
        "aturan_jalan": aturan_jalan,
        "waktu_ms": round((time.perf_counter() - mulai) * 1000, 3),
    }


def kumpulkan_jawaban(kb):
    """Tanyakan setiap gejala di terminal. Mengembalikan {kode_gejala: cf_pengguna}."""
    skala = kb["skala_cf_pengguna"]
    print("=== Sistem Pakar Diagnosis Penyakit Tanaman Kopi ===")
    print("Pilih tingkat keyakinan untuk setiap gejala:")
    for i, s in enumerate(skala):
        print(f"  {i} = {s['label']}")
    print("Tekan Enter untuk 'Tidak tahu'.\n")

    jawaban = {}
    urutan = kb.get("urutan_bagian") or sorted({g["bagian"] for g in kb["gejala"].values()})
    for bagian in urutan:
        daftar = [(k, g) for k, g in kb["gejala"].items() if g["bagian"] == bagian]
        if not daftar:
            continue
        print(f"--- {bagian} ---")
        for kode, g in daftar:
            while True:
                isi = input(f"{kode} {g['nama']}? ").strip()
                if isi == "":
                    isi = "0"
                if isi.isdigit() and int(isi) < len(skala):
                    break
                print(f"  Masukkan angka 0-{len(skala) - 1}.")
            nilai = skala[int(isi)]["nilai"]
            if nilai > 0:
                jawaban[kode] = nilai
    return jawaban


def tampilkan_hasil(out, judul="Hasil diagnosis"):
    """Cetak keluaran diagnosis() atau diagnosis_ds() ke terminal."""
    tampil = [h for h in out["hasil"] if h["tampil"]]
    print(f"\n=== {judul} ===")
    if not tampil:
        print("Gejala belum cukup untuk menyimpulkan penyakit. Tambah gejala atau hubungi penyuluh.")
    for i, h in enumerate(tampil, 1):
        print(f"{i}. {h['nama']} ({h['kode']}): {h['persen']}%")
        if i == 1:
            print(f"   Penanganan: {h['solusi']}")
    for f in out["fakta_antara"]:
        print(f"\nPerhatian ({f['nama']}): {f['saran']}")
    print("\n--- Langkah perhitungan ---")
    for baris in out["jejak"]:
        print(baris)
    print(f"\nWaktu proses: {out['waktu_ms']} ms")
    print("Hasil ini diagnosis awal. Konfirmasikan ke penyuluh.")


def tanya_jawab(fungsi=diagnosis):
    """Mode tanya-jawab di terminal untuk demo."""
    kb = muat_kb()
    jawaban = kumpulkan_jawaban(kb)
    if not jawaban:
        print("\nSemua gejala 'Tidak tahu'. Pilih minimal satu gejala.")
        return
    tampilkan_hasil(fungsi(jawaban, kb))


if __name__ == "__main__":
    tanya_jawab()
