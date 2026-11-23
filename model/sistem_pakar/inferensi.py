"""Mesin inferensi: Forward Chaining + Certainty Factor (CF).

Alur diagnosis():
    periksa_masukan -> forward_chaining (cf_aturan, gabung_cf) -> susun_hasil -> buat_keluaran

Rumus CF:
    satu premis  : CF premis x CF pakar
    premis DAN   : min(CF premis) x CF pakar
    gabung       : lihat gabung_cf()
"""

import time

from .basis_pengetahuan import muat_kb
from .kontrak import angka, buat_keluaran, periksa_masukan, susun_hasil, teks_fakta_awal


# ---------------------------------------------------------------------------
# Rumus Certainty Factor
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Forward Chaining dan diagnosis
# ---------------------------------------------------------------------------

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
