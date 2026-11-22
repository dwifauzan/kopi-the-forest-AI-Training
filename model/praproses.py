"""Praproses: ubah data mentah (deskripsi penyakit dari literatur) menjadi kasus uji siap pakai.

Alur:
    data/mentah/*.csv
      -> saring_baris(): cek kategori, label, pemetaan penyakit, gejala dari teks
      -> gabungkan deskripsi kembar (penyakit + gejala sama = satu kasus)
      -> data/bersih/kasus_literatur.csv  (kasus L01, L02, ...)
      -> data/bersih/ditolak.csv          (baris yang dibuang + alasannya)

Prinsipnya: data mentah tidak pernah diedit, dan kode menyesuaikan dataset.
- Pemetaan label penyakit -> kode P ada di data/pemetaan/penyakit.csv
  (kode "-" = tanaman sehat, kode kosong = di luar cakupan basis pengetahuan).
- Pemetaan frasa gejala (regex) -> kode G ada di data/pemetaan/gejala.csv.
- Nama kolom data mentah diatur di KOLOM.
Kalau dataset bertambah atau berubah, ubah tabel/konstanta itu, bukan logikanya.

    python praproses.py [mentah.csv] [bersih.csv]
"""

import csv
import json
import os
import re
import sys

from inferensi import muat_kb

FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(FOLDER, "data")
MENTAH = os.path.join(DATA, "mentah", "leafnet_coffee_kb.csv")
BERSIH = os.path.join(DATA, "bersih", "kasus_literatur.csv")
DITOLAK = os.path.join(DATA, "bersih", "ditolak.csv")
PEMETAAN_PENYAKIT = os.path.join(DATA, "pemetaan", "penyakit.csv")
PEMETAAN_GEJALA = os.path.join(DATA, "pemetaan", "gejala.csv")

# Nama kolom di data mentah. Ubah nilai di kanan kalau sumber data memakai nama lain.
KOLOM = {
    "id": "id",
    "penyakit": "disease",
    "teks": "answer",
    "sumber": "source",       # opsional
    "kategori": "category",   # opsional; kalau tidak ada, semua baris dianggap identifikasi penyakit
}
KOLOM_OPSIONAL = {"sumber", "kategori"}
KATEGORI_DIPAKAI = {"disease_identification"}

# CF pengguna untuk gejala yang disebut jelas di deskripsi literatur.
# Konvensi kelompok, bukan nilai dari sumber: sebutkan di laporan.
CF_LITERATUR = 1.0
AWALAN_KODE = "L"

# Kata penyangkal sebelum frasa gejala di kalimat yang sama ("no spots" bukan gejala).
PENYANGKAL = re.compile(r"\b(no|not|without|absence of)\b[^.;]{0,40}$", re.I)

KOLOM_BERSIH = ["kode", "gejala", "diagnosis_pakar", "sumber", "catatan"]
KOLOM_DITOLAK = ["id", "penyakit", "alasan"]


# ---------------------------------------------------------------------------
# Baca/tulis file
# ---------------------------------------------------------------------------

def baca_csv(path):
    """Baca CSV menjadi list of dict (header = kunci). Aman untuk file berawalan BOM dari Excel."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


# ---------------------------------------------------------------------------
# Pemetaan
# ---------------------------------------------------------------------------

def muat_pemetaan(kb, path_penyakit=PEMETAAN_PENYAKIT, path_gejala=PEMETAAN_GEJALA):
    """Baca kedua tabel pemetaan dan pastikan semua kodenya ada di basis pengetahuan.

    Mengembalikan:
        (peta_penyakit, pola_gejala)
        - peta_penyakit: {label_huruf_kecil: {"kode": "P01" | "-" | "", "catatan": str}}
        - pola_gejala  : [(regex_terkompilasi, kode_gejala), ...] sesuai urutan di file

    Error:
        ValueError kalau ada kode yang tidak dikenal, label dipetakan ke dua kode berbeda,
        atau pola regex tidak valid. Pesannya menyebut file dan isinya.
    """
    peta_penyakit = {}
    for b in baca_csv(path_penyakit):
        kode = b["kode"].strip()
        label = b["label_sumber"].strip().lower()
        if kode not in ("", "-") and kode not in kb["penyakit"]:
            raise ValueError(f"pemetaan/penyakit.csv: kode {kode} tidak ada di basis pengetahuan")
        if label in peta_penyakit and peta_penyakit[label]["kode"] != kode:
            raise ValueError(f"pemetaan/penyakit.csv: label '{b['label_sumber']}' dipetakan ke dua kode berbeda")
        peta_penyakit[label] = {"kode": kode, "catatan": b["catatan"]}

    pola_gejala = []
    for b in baca_csv(path_gejala):
        kode = b["kode_gejala"].strip()
        if kode not in kb["gejala"]:
            raise ValueError(f"pemetaan/gejala.csv: kode {kode} tidak ada di basis pengetahuan")
        try:
            pola_gejala.append((re.compile(b["pola"], re.I), kode))
        except re.error as e:
            raise ValueError(f"pemetaan/gejala.csv: pola '{b['pola']}' tidak valid ({e})") from None
    return peta_penyakit, pola_gejala


def gejala_tanpa_pola(kb, pola_gejala=None):
    """Gejala di basis pengetahuan yang belum punya pola di pemetaan/gejala.csv.

    Gejala seperti ini tidak akan pernah terbaca dari teks literatur.
    pola_gejala kosong = dibaca dari file pemetaan.
    """
    if pola_gejala is None:
        pola_gejala = muat_pemetaan(kb)[1]
    ada = {kode for _, kode in pola_gejala}
    return [k for k in kb["gejala"] if k not in ada]


def cari_gejala(teks, pola_gejala):
    """Cari gejala yang disebut di teks deskripsi.

    Untuk setiap pola, diambil kecocokan pertama yang tidak didahului kata penyangkal
    di kalimat yang sama.

    Mengembalikan:
        {kode_gejala: frasa_yang_cocok}, urut kode. Contoh: {"G02": "defoliation"}
    """
    ketemu = {}
    for pola, kode in pola_gejala:
        for m in pola.finditer(teks):
            if not PENYANGKAL.search(teks[:m.start()]):
                ketemu.setdefault(kode, m.group(0))
                break
    return dict(sorted(ketemu.items()))


# ---------------------------------------------------------------------------
# Praproses
# ---------------------------------------------------------------------------

def ambil(baris, kunci):
    """Ambil nilai kolom `kunci` (nama di KOLOM) dari satu baris mentah, sudah di-strip."""
    return (baris.get(KOLOM[kunci]) or "").strip()


def periksa_kolom(mentah):
    """Pastikan kolom wajib ada di data mentah.

    Mengembalikan:
        set nama kolom yang ada.

    Error:
        ValueError kalau kolom wajib tidak ada.
    """
    ada = set(mentah[0]) if mentah else set()
    hilang = [v for k, v in KOLOM.items() if k not in KOLOM_OPSIONAL and v not in ada]
    if mentah and hilang:
        raise ValueError(f"Kolom wajib tidak ada di data mentah: {', '.join(hilang)}")
    return ada


def saring_baris(baris, peta_penyakit, pola_gejala, ada_kategori):
    """Putuskan satu baris mentah dipakai atau ditolak.

    Urutan pemeriksaan:
    1. kategori bukan identifikasi penyakit (kalau kolom kategori ada)
    2. label penyakit atau teks kosong
    3. label belum ada di pemetaan/penyakit.csv
    4. penyakit di luar cakupan basis pengetahuan (kode kosong)
    5. penyakit tanpa gejala yang terbaca dari teks
    6. label sehat ("-") tetapi teksnya menyebut gejala

    Mengembalikan:
        (kode_penyakit, gejala, alasan). Kalau alasan tidak kosong, baris ditolak.
        gejala = {kode_gejala: frasa}, hasil cari_gejala().
    """
    label, teks = ambil(baris, "penyakit"), ambil(baris, "teks")
    if ada_kategori and ambil(baris, "kategori") not in KATEGORI_DIPAKAI:
        return None, {}, f"kategori '{ambil(baris, 'kategori')}' bukan identifikasi penyakit"
    if not label or not teks:
        return None, {}, "label penyakit atau teks deskripsi kosong"

    peta = peta_penyakit.get(label.lower())
    if peta is None:
        return None, {}, "label belum ada di pemetaan/penyakit.csv"
    if not peta["kode"]:
        return None, {}, f"luar cakupan basis pengetahuan ({peta['catatan']})"

    kode = peta["kode"]
    gejala = cari_gejala(teks, pola_gejala)
    if kode != "-" and not gejala:
        return kode, gejala, "tidak ada gejala di teks yang cocok dengan pemetaan/gejala.csv"
    if kode == "-" and gejala:
        return kode, gejala, (f"label sehat tetapi teks menyebut gejala {', '.join(gejala)}; "
                              "periksa data atau pola")
    return kode, gejala, ""


def praproses(path_mentah=MENTAH, path_bersih=BERSIH, path_ditolak=DITOLAK, kb=None):
    """Saring data mentah menjadi kasus uji, lalu tulis file bersih dan file ditolak.

    Baris dengan penyakit dan gejala yang sama digabung menjadi satu kasus; kolom
    "sumber" kasus itu berisi semua id barisnya (misalnya "coffee_kb_1; coffee_kb_2").

    Mengembalikan:
        (kasus, ditolak)
        - kasus  : [{"kode", "gejala", "diagnosis_pakar", "sumber", "catatan"}, ...]
        - ditolak: [{"id", "penyakit", "alasan"}, ...]
    """
    kb = kb or muat_kb()
    peta_penyakit, pola_gejala = muat_pemetaan(kb)
    mentah = baca_csv(path_mentah)
    ada_kategori = KOLOM["kategori"] in periksa_kolom(mentah)

    terkumpul = {}   # (kode_penyakit, kode_gejala...) -> kasus
    ditolak = []
    for b in mentah:
        kode, gejala, alasan = saring_baris(b, peta_penyakit, pola_gejala, ada_kategori)
        if alasan:
            ditolak.append({"id": ambil(b, "id"), "penyakit": ambil(b, "penyakit"), "alasan": alasan})
            continue

        kunci = (kode, *gejala)
        if kunci in terkumpul:
            terkumpul[kunci]["sumber"] += f"; {ambil(b, 'id')}"
            continue
        frasa = "; ".join(f"'{f}' -> {g}" for g, f in gejala.items()) or "tanpa gejala"
        terkumpul[kunci] = {
            "gejala": "; ".join(f"{g}={CF_LITERATUR:g}" for g in gejala),
            "diagnosis_pakar": kode,
            "sumber": ambil(b, "id"),
            "catatan": f"{ambil(b, 'penyakit')}. {frasa}. Sumber: {ambil(b, 'sumber') or 'tidak disebutkan'}",
        }

    kasus = [{"kode": f"{AWALAN_KODE}{i:02d}", **k} for i, k in enumerate(terkumpul.values(), 1)]
    tulis_csv(path_bersih, KOLOM_BERSIH, kasus)
    tulis_csv(path_ditolak, KOLOM_DITOLAK, ditolak)
    return kasus, ditolak


def cetak(kasus, ditolak, path_bersih=BERSIH, path_ditolak=DITOLAK):
    """Cetak ringkasan praproses: kasus yang lolos, baris yang ditolak, dan gejala tanpa pola."""
    print(f"Kasus siap pakai: {len(kasus)}")
    for k in kasus:
        print(f"  {k['kode']}  {k['diagnosis_pakar']:3}  {k['gejala'] or '(tanpa gejala)':22}  dari {k['sumber']}")
    print(f"\nBaris ditolak: {len(ditolak)}")
    for d in ditolak:
        print(f"  {d['id']:13} {d['penyakit']:26} {d['alasan']}")
    belum = gejala_tanpa_pola(muat_kb())
    if belum:
        print(f"\nPeringatan: gejala tanpa pola di pemetaan/gejala.csv, tidak akan terbaca dari teks: "
              f"{', '.join(belum)}")
    print(f"\nDitulis ke {path_bersih}\n       dan {path_ditolak}")


if __name__ == "__main__":
    path = sys.argv[1:3]
    kasus, ditolak = praproses(*path)
    cetak(kasus, ditolak, *path[1:2])
