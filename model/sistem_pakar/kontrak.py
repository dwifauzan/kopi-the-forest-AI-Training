"""Kontrak masukan dan keluaran, dipakai bersama oleh semua metode (CF dan DS).

- Masukan : {kode_gejala: cf_pengguna}, divalidasi oleh periksa_masukan().
            urai_gejala() mengubah teks "G01=0.8; G02=0.6" menjadi bentuk itu.
- Keluaran: dict dari buat_keluaran(), dengan daftar hasil dari susun_hasil().

Dengan satu tempat seperti ini, metode baru otomatis punya bentuk keluaran yang sama.
"""

import re
import time



# ---------------------------------------------------------------------------
# Masukan
# ---------------------------------------------------------------------------

def urai_gejala(teks):
    """Ubah teks gejala menjadi dict masukan diagnosis.

    Format yang diterima:
        "G01=0.8; G02=0.6"   (pemisah titik koma)
        "G01=0,8; G02=0,6"   (desimal koma, gaya Indonesia)
        "G01=0.8, G02=0.6"   (pemisah koma, asalkan diikuti kode G)

    Mengembalikan:
        {"G01": 0.8, "G02": 0.6}. Teks kosong -> {}.

    Error:
        ValueError kalau ada bagian yang nilainya bukan angka.
    """
    hasil = {}
    for bagian in re.split(r";|,(?=\s*[Gg]\d)", teks or ""):
        bagian = bagian.strip()
        if not bagian:
            continue
        kode, _, nilai = bagian.partition("=")
        try:
            hasil[kode.strip().upper()] = float(nilai.strip().replace(",", "."))
        except ValueError:
            raise ValueError(f"Format gejala salah: '{bagian}' (contoh benar: G01=0.8)") from None
    return hasil


def periksa_masukan(input_pengguna, kb):
    """Validasi masukan pengguna dan buang gejala yang dijawab "Tidak tahu" (CF 0).

    Parameter:
        input_pengguna: {kode_gejala: cf_pengguna}, misalnya {"G01": 0.8}. Boleh None.

    Mengembalikan:
        {kode_gejala: cf_pengguna} yang CF-nya > 0.

    Error:
        ValueError kalau masukan bukan dict, kode gejala tidak dikenal, CF bukan angka
        (angka dalam teks seperti "0.8" diterima), atau CF di luar 0..1.
        Rute web sebaiknya menangkap error ini dan membalas status 400.
    """
    if input_pengguna is not None and not isinstance(input_pengguna, dict):
        raise ValueError("Masukan gejala harus berupa {kode_gejala: cf}, misalnya {\"G01\": 0.8}")
    fakta = {}
    for kode, cf in (input_pengguna or {}).items():
        if kode not in kb["gejala"]:
            raise ValueError(f"Kode gejala tidak dikenal: {kode}")
        try:
            if isinstance(cf, bool):
                raise TypeError
            cf = float(cf)
        except (TypeError, ValueError):
            raise ValueError(f"CF pengguna untuk {kode} harus angka 0 sampai 1, bukan {cf!r}") from None
        if not 0 <= cf <= 1:
            raise ValueError(f"CF pengguna untuk {kode} harus di antara 0 dan 1, bukan {cf}")
        if cf > 0:
            fakta[kode] = cf
    return fakta

# ---------------------------------------------------------------------------
# Keluaran
# ---------------------------------------------------------------------------

def angka(x):
    """Format angka untuk teks jejak: maksimal 4 desimal, tanpa nol di belakang (0.8, bukan 0.8000)."""
    s = f"{round(x, 4):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def teks_fakta_awal(fakta):
    """Baris pertama jejak, misalnya "Fakta awal: G01 (0.8), G02 (0.6)"."""
    if not fakta:
        return "Fakta awal: tidak ada gejala yang dipilih"
    return "Fakta awal: " + ", ".join(f"{k} ({angka(v)})" for k, v in fakta.items())


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

# ---------------------------------------------------------------------------
# Membaca keluaran
# ---------------------------------------------------------------------------

def diagnosis_teratas(out):
    """Ambil diagnosis sistem dari keluaran diagnosis()/diagnosis_ds().

    Mengembalikan:
        (kode, persen, seri)
        - kode  : "P01", atau "P05/P06/P07" kalau seri, atau "-" kalau tidak ada yang tampil
        - persen: persen penyakit teratas, "" kalau tidak ada
        - seri  : True kalau lebih dari satu penyakit di puncak
    """
    tampil = [h for h in out["hasil"] if h["tampil"]]
    if not tampil:
        return "-", "", False
    puncak = [h["kode"] for h in tampil if h["cf"] == tampil[0]["cf"]]
    return "/".join(puncak), tampil[0]["persen"], len(puncak) > 1


def ringkas_hasil(out):
    """Maksimal tiga penyakit teratas yang tampil, misalnya "P01 80.65%, P03 36.0%"."""
    tampil = [f"{h['kode']} {h['persen']}%" for h in out["hasil"] if h["tampil"]][:3]
    return ", ".join(tampil) or "tidak ada yang tampil"
