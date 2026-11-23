"""Lembar kasus "buta" untuk pakar: sumber kasus uji berlabel tanpa mengarang diagnosis.

Alur:
    1. buat_lembar()  : susun kombinasi gejala dari basis pengetahuan, urutan diacak,
                        kolom diagnosis DIKOSONGKAN, hasil sistem TIDAK ditampilkan.
                        -> data/lembar_pakar/lembar_pakar.csv   (diberikan ke pakar)
                        -> data/lembar_pakar/kunci_internal.csv (JANGAN diberikan ke pakar)
                        -> data/lembar_pakar/PETUNJUK.md        (dibacakan/diberikan ke pakar)
    2. Pakar mengisi diagnosis_pakar (kode P.., "-", atau nama penyakit lain).
    3. impor_lembar() : salin baris yang sudah diisi ke data/kasus_uji.csv.
    4. python main.py evaluasi

Diagnosis selalu dari pakar. Kode ini hanya menyusun pertanyaan.

Jenis kasus (dibentuk otomatis dari isi basis pengetahuan, jadi ikut berubah kalau data berubah):
- khas     : semua gejala positif satu penyakit, keyakinan kuat
- sebagian : gejala terkuat satu penyakit saja, keyakinan sedang
- lemah    : gejala terlemah satu penyakit, keyakinan lemah
- negatif  : gejala terkuat penyakit + gejala yang menurunkan CF-nya (aturan CF negatif)
- gabungan : premis aturan DAN (misalnya G12 + G13), keyakinan kuat
- campuran : gejala terkuat dua penyakit berbeda, keyakinan sedang
- acak     : 2-3 gejala acak dengan keyakinan acak, mengurangi bias kasus buatan dari aturan
Kasus dengan gejala yang sama persis hanya dimasukkan sekali.

    python main.py lembar [--timpa]
    python main.py impor-pakar data/lembar_pakar/lembar_pakar.csv
"""

import csv
import itertools
import os
import random

from sistem_pakar import daftar_pertanyaan, muat_kb, urai_gejala
from sistem_pakar.kontrak import periksa_masukan

from .berkas_csv import baca_csv, kolom_csv, tulis_csv
from .lokasi import FOLDER_LEMBAR, KASUS_UJI

NAMA_LEMBAR = "lembar_pakar.csv"
NAMA_KUNCI = "kunci_internal.csv"
NAMA_PETUNJUK = "PETUNJUK.md"

SEED = 2026            # acakan tetap: lembar yang dibuat ulang isinya sama
JUMLAH_CAMPURAN = 6
JUMLAH_ACAK = 6
AWALAN_KODE = "K"

KOLOM_LEMBAR = ["kode", "gejala_dibaca", "gejala", "diagnosis_pakar", "catatan",
                "nama_pakar", "tanggal", "lokasi"]
KOLOM_KUNCI = ["kode", "jenis", "dibentuk_dari", "gejala"]
KOLOM_KASUS = ["kode", "gejala", "diagnosis_pakar", "tanggal", "lokasi", "nama_pakar", "catatan"]
KOLOM_WAJIB_LEMBAR = ["kode", "gejala", "diagnosis_pakar"]

# ---------------------------------------------------------------------------
# Menyusun kasus
# ---------------------------------------------------------------------------

def tingkat_keyakinan(kb):
    """Ambil tiga tingkat keyakinan dari skala CF pengguna.

    Mengembalikan:
        {"lemah": nilai terkecil > 0, "sedang": nilai kedua, "kuat": nilai kedua terbesar}
        Dengan skala sekarang: 0.4, 0.6, 0.8. "Pasti" (1.0) tidak dipakai supaya kasus
        tidak terlalu mudah.
    """
    nilai = sorted({s["nilai"] for s in kb["skala_cf_pengguna"] if s["nilai"] > 0})
    return {"lemah": nilai[0], "sedang": nilai[min(1, len(nilai) - 1)], "kuat": nilai[max(0, len(nilai) - 2)]}


def gejala_penyakit(kb):
    """Gejala positif satu premis per penyakit, urut dari CF pakar terbesar.

    Mengembalikan:
        {kode_penyakit: [kode_gejala, ...]}. Penyakit tanpa aturan seperti itu tidak dimasukkan.
    """
    hasil = {}
    for p in kb["penyakit"]:
        aturan = [r for r in kb["aturan"] if r["maka"] == p and len(r["jika"]) == 1 and r["cf"] > 0]
        aturan.sort(key=lambda r: -r["cf"])
        if aturan:
            hasil[p] = [r["jika"][0] for r in aturan]
    return hasil


def susun_kasus(kb, seed=SEED):
    """Bentuk semua kasus lembar dari basis pengetahuan, lalu acak urutannya.

    Mengembalikan:
        [{"kode", "jenis", "dibentuk_dari", "gejala": {kode_gejala: cf}}, ...]
        "dibentuk_dari" hanya catatan internal asal kasus, BUKAN diagnosis.
    """
    acak = random.Random(seed)
    t = tingkat_keyakinan(kb)
    per_penyakit = gejala_penyakit(kb)
    calon = []

    for p, gejala in per_penyakit.items():
        calon.append(("khas", p, {g: t["kuat"] for g in gejala}))
        calon.append(("sebagian", p, {gejala[0]: t["sedang"]}))
        calon.append(("lemah", p, {gejala[-1]: t["lemah"]}))

    for r in kb["aturan"]:
        if r["cf"] < 0 and len(r["jika"]) == 1 and r["maka"] in per_penyakit:
            calon.append(("negatif", r["maka"], {per_penyakit[r["maka"]][0]: t["kuat"], r["jika"][0]: t["kuat"]}))
        if len(r["jika"]) > 1 and all(g in kb["gejala"] for g in r["jika"]):
            calon.append(("gabungan", r["maka"], {g: t["kuat"] for g in r["jika"]}))

    pasangan = [(p, q) for p, q in itertools.combinations(per_penyakit, 2)
                if not set(per_penyakit[p]) & set(per_penyakit[q])]
    for p, q in acak.sample(pasangan, min(JUMLAH_CAMPURAN, len(pasangan))):
        calon.append(("campuran", f"{p}+{q}", {per_penyakit[p][0]: t["sedang"], per_penyakit[q][0]: t["sedang"]}))

    ditanya = [k for _, daftar in daftar_pertanyaan(kb) for k, _ in daftar]
    pilihan_cf = sorted(set(t.values()))
    for _ in range(JUMLAH_ACAK):
        gejala = acak.sample(ditanya, min(acak.choice([2, 3]), len(ditanya)))
        calon.append(("acak", "-", {g: acak.choice(pilihan_cf) for g in gejala}))

    kasus, dilihat = [], set()
    for jenis, asal, gejala in calon:
        kunci = frozenset(gejala.items())
        if kunci not in dilihat:
            dilihat.add(kunci)
            kasus.append({"jenis": jenis, "dibentuk_dari": asal, "gejala": gejala})

    acak.shuffle(kasus)
    for i, k in enumerate(kasus, 1):
        k["kode"] = f"{AWALAN_KODE}{i:02d}"
    return kasus


def teks_gejala(gejala, kb):
    """Tulis gejala untuk dua kolom lembar, urut sesuai urutan pertanyaan.

    Mengembalikan:
        (dibaca, kode)
        - dibaca: "[Daun] Daun gugur: Kemungkinan besar | [Tajuk] Pohon gundul: Mungkin"
        - kode  : "G02=0.6; G03=0.4" (format yang dibaca evaluasi.py)
    """
    label = {s["nilai"]: s["label"] for s in kb["skala_cf_pengguna"]}
    urutan = [k for _, daftar in daftar_pertanyaan(kb) for k, _ in daftar]
    kode_urut = sorted(gejala, key=lambda g: urutan.index(g) if g in urutan else len(urutan))
    dibaca = " | ".join(f"[{kb['gejala'][g]['bagian']}] {kb['gejala'][g]['nama']}: "
                        f"{label.get(gejala[g], gejala[g])}" for g in kode_urut)
    return dibaca, "; ".join(f"{g}={gejala[g]:g}" for g in kode_urut)

# ---------------------------------------------------------------------------
# Membuat lembar
# ---------------------------------------------------------------------------

def lembar_sudah_diisi(path):
    """True kalau lembar di path sudah ada dan minimal satu diagnosis_pakar terisi."""
    if not os.path.exists(path):
        return False
    return any((b.get("diagnosis_pakar") or "").strip() for b in baca_csv(path))


def tulis_petunjuk(path, kb, jumlah):
    """Tulis PETUNJUK.md untuk pakar: cara mengisi dan daftar kode penyakit."""
    penyakit = "\n".join(f"| {k} | {p['nama']} | {p['penyebab']} |" for k, p in kb["penyakit"].items())
    skala = "\n".join(f"- **{s['label']}**: {s['arti']}" for s in kb["skala_cf_pengguna"] if s["nilai"] > 0)
    isi = f"""# Petunjuk pengisian lembar kasus

Lembar `{NAMA_LEMBAR}` berisi {jumlah} kasus. Setiap kasus adalah gejala yang dilihat
petani pada satu tanaman kopi, beserta seberapa yakin petani melihat gejala itu:

{skala}

Gejala yang tidak disebut dianggap tidak terlihat atau tidak diketahui.

## Yang diisi
1. **diagnosis_pakar**: penyakit yang paling mungkin menurut Bapak/Ibu.
   - Tulis **kodenya** dari tabel di bawah, misalnya `P01`.
   - Tulis `-` kalau gejalanya belum cukup untuk menyimpulkan penyakit apa pun.
   - Kalau penyakitnya tidak ada di tabel, tulis **nama penyakitnya** langsung.
2. **catatan** (boleh kosong): alasan, kemungkinan penyakit lain, atau pemeriksaan tambahan yang perlu.
3. **nama_pakar, tanggal, lokasi**: cukup diisi di baris pertama.

Kolom `gejala` jangan diubah; kolom itu dibaca oleh program.
Mohon dinilai berdasarkan pengalaman Bapak/Ibu, tanpa melihat hasil aplikasi.

## Kode penyakit

| Kode | Nama | Penyebab |
|---|---|---|
{penyakit}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(isi)


def buat_lembar(kb=None, folder=FOLDER_LEMBAR, seed=SEED, timpa=False):
    """Buat lembar pakar, kunci internal, dan petunjuk di `folder`.

    Parameter:
        timpa: False = menolak menimpa lembar yang diagnosisnya sudah mulai diisi.

    Mengembalikan:
        daftar kasus dari susun_kasus().

    Error:
        FileExistsError kalau lembar sudah diisi dan timpa=False.
    """
    kb = kb or muat_kb()
    path_lembar = os.path.join(folder, NAMA_LEMBAR)
    if not timpa and lembar_sudah_diisi(path_lembar):
        raise FileExistsError(f"{path_lembar} sudah berisi diagnosis pakar. Impor dulu, "
                              "atau pakai --timpa kalau memang ingin membuat ulang.")

    kasus = susun_kasus(kb, seed)
    lembar, kunci = [], []
    for k in kasus:
        dibaca, kode_gejala = teks_gejala(k["gejala"], kb)
        lembar.append({"kode": k["kode"], "gejala_dibaca": dibaca, "gejala": kode_gejala,
                       "diagnosis_pakar": "", "catatan": "", "nama_pakar": "", "tanggal": "", "lokasi": ""})
        kunci.append({"kode": k["kode"], "jenis": k["jenis"], "dibentuk_dari": k["dibentuk_dari"],
                      "gejala": kode_gejala})

    os.makedirs(folder, exist_ok=True)
    # utf-8-sig supaya langsung terbaca benar di Excel
    with open(path_lembar, "w", encoding="utf-8-sig", newline="") as f:
        tulis = csv.DictWriter(f, fieldnames=KOLOM_LEMBAR)
        tulis.writeheader()
        tulis.writerows(lembar)
    tulis_csv(os.path.join(folder, NAMA_KUNCI), KOLOM_KUNCI, kunci)
    tulis_petunjuk(os.path.join(folder, NAMA_PETUNJUK), kb, len(kasus))
    return kasus

# ---------------------------------------------------------------------------
# Impor hasil pakar
# ---------------------------------------------------------------------------

def impor_lembar(path_lembar, path_kasus=KASUS_UJI, kb=None):
    """Salin baris lembar yang sudah diisi pakar ke file kasus uji.

    - Baris dengan diagnosis_pakar kosong dilewati.
    - Baris yang kodenya sudah ada di file kasus dilewati (impor ulang aman).
    - nama_pakar, tanggal, dan lokasi yang kosong diisi dari baris pertama yang mengisinya.

    Mengembalikan:
        (ditambah, dilewati, peringatan)
        - ditambah  : list kode kasus yang ditambahkan
        - dilewati  : [(kode, alasan), ...]
        - peringatan: list pesan (misalnya nama pakar kosong)

    Error:
        ValueError kalau kolom wajib lembar tidak ada (misalnya file tersimpan dengan format lain),
        atau kolom gejala rusak/berisi kode gejala tidak dikenal (pesan menyebut kode kasus).
    """
    kb = kb or muat_kb()
    hilang = [k for k in KOLOM_WAJIB_LEMBAR if k not in kolom_csv(path_lembar)]
    if hilang:
        raise ValueError(f"{path_lembar}: kolom wajib tidak ada: {', '.join(hilang)}. "
                         "Simpan lembar sebagai CSV tanpa mengubah baris judul kolom.")
    lembar = baca_csv(path_lembar)
    lama, kolom = [], KOLOM_KASUS
    if os.path.exists(path_kasus):
        lama = baca_csv(path_kasus)
        kolom = kolom_csv(path_kasus) or KOLOM_KASUS   # header tetap dipakai walau file kosong
    sudah_ada = {b["kode"] for b in lama}

    bawaan = {k: next((b[k].strip() for b in lembar if (b.get(k) or "").strip()), "")
              for k in ("nama_pakar", "tanggal", "lokasi")}

    ditambah, dilewati, baru = [], [], []
    for b in lembar:
        kode = (b.get("kode") or "").strip()
        diagnosis = (b.get("diagnosis_pakar") or "").strip()
        if not kode:
            continue
        if not diagnosis:
            dilewati.append((kode, "diagnosis pakar belum diisi"))
            continue
        if kode in sudah_ada:
            dilewati.append((kode, f"kode sudah ada di {os.path.basename(path_kasus)}"))
            continue
        try:
            periksa_masukan(urai_gejala(b["gejala"]), kb)
        except ValueError as e:
            raise ValueError(f"Kasus {kode}: {e}") from None

        isi = {
            "kode": kode,
            "gejala": b["gejala"],
            "diagnosis_pakar": diagnosis.upper() if diagnosis.upper() in kb["penyakit"] else diagnosis,
            "tanggal": (b.get("tanggal") or "").strip() or bawaan["tanggal"],
            "lokasi": (b.get("lokasi") or "").strip() or bawaan["lokasi"],
            "nama_pakar": (b.get("nama_pakar") or "").strip() or bawaan["nama_pakar"],
            "catatan": " ".join(x for x in [(b.get("catatan") or "").strip(), "(lembar kasus buta)"] if x),
        }
        baru.append({k: isi.get(k, "") for k in kolom})
        ditambah.append(kode)

    peringatan = []
    if ditambah and not bawaan["nama_pakar"]:
        peringatan.append("nama_pakar kosong; isi supaya sumber kasus bisa dipertanggungjawabkan")
    if ditambah:
        tulis_csv(path_kasus, kolom, [{k: b.get(k, "") for k in kolom} for b in lama] + baru)
    return ditambah, dilewati, peringatan


def cetak_lembar(kasus, folder=FOLDER_LEMBAR):
    """Cetak ringkasan lembar yang dibuat: jumlah per jenis dan lokasi file."""
    jumlah = {}
    for k in kasus:
        jumlah[k["jenis"]] = jumlah.get(k["jenis"], 0) + 1
    print(f"Lembar kasus buta: {len(kasus)} kasus "
          f"({', '.join(f'{j} {n}' for j, n in jumlah.items())})")
    print(f"  Berikan ke pakar : {os.path.join(folder, NAMA_LEMBAR)}")
    print(f"                     {os.path.join(folder, NAMA_PETUNJUK)}")
    print(f"  JANGAN diberikan : {os.path.join(folder, NAMA_KUNCI)} (asal tiap kasus, untuk analisis)")
    print("Setelah diisi: python main.py impor-pakar <lembar.csv>, lalu python main.py evaluasi")


def cetak_impor(ditambah, dilewati, peringatan, path_kasus=KASUS_UJI):
    """Cetak hasil impor: kasus yang ditambahkan, yang dilewati, dan peringatan."""
    print(f"Ditambahkan ke {path_kasus}: {len(ditambah)} kasus")
    if ditambah:
        print("  " + ", ".join(ditambah))
    per_alasan = {}
    for kode, alasan in dilewati:
        per_alasan.setdefault(alasan, []).append(kode)
    for alasan, kode in per_alasan.items():
        print(f"Dilewati ({alasan}): {len(kode)} kasus, {', '.join(kode[:10])}{' ...' if len(kode) > 10 else ''}")
    for p in peringatan:
        print(f"Peringatan: {p}")
