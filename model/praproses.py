"""Praproses data mentah menjadi kasus uji yang siap dipakai evaluasi.

Alur: data mentah (CSV) -> saring -> petakan penyakit -> petakan gejala -> buang duplikat
      -> data/bersih/kasus_literatur.csv (+ data/bersih/ditolak.csv berisi alasan penolakan)

Aturan pemetaan tidak ditulis di kode, tetapi di data/pemetaan/penyakit.csv dan
data/pemetaan/gejala.csv. Kalau datanya bertambah, ubah tabel itu, bukan kodenya.

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

# Nama kolom di data mentah. Sesuaikan di sini kalau sumber datanya memakai nama lain.
KOLOM = {
    "id": "id",
    "penyakit": "disease",
    "teks": "answer",
    "sumber": "source",       # opsional
    "kategori": "category",   # opsional; kalau tidak ada, semua baris dianggap identifikasi penyakit
}
KOLOM_OPSIONAL = {"sumber", "kategori"}
KATEGORI_DIPAKAI = {"disease_identification"}

# CF pengguna untuk gejala yang disebut eksplisit di deskripsi literatur (konvensi kelompok,
# bukan nilai dari sumber; sebutkan di laporan).
CF_LITERATUR = 1.0
AWALAN_KODE = "L"
PENYANGKAL = re.compile(r"\b(no|not|without|absence of)\b[^.;]{0,40}$", re.I)

KOLOM_BERSIH = ["kode", "gejala", "diagnosis_pakar", "sumber", "catatan"]
KOLOM_DITOLAK = ["id", "penyakit", "alasan"]


def jsonl_ke_csv(path_jsonl, path_csv):
    """Ubah data mentah JSONL (satu objek per baris) menjadi CSV mentah, tanpa mengubah isinya."""
    with open(path_jsonl, encoding="utf-8") as f:
        baris = [json.loads(l) for l in f if l.strip()]
    kolom = []
    for b in baris:
        kolom += [k for k in b if k not in kolom]
    os.makedirs(os.path.dirname(path_csv) or ".", exist_ok=True)
    with open(path_csv, "w", encoding="utf-8", newline="") as f:
        tulis = csv.DictWriter(f, fieldnames=kolom)
        tulis.writeheader()
        for b in baris:
            tulis.writerow({k: "" if b.get(k) is None else b.get(k) for k in kolom})
    return len(baris)


def baca_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def tulis_csv(path, kolom, baris):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        tulis = csv.DictWriter(f, fieldnames=kolom)
        tulis.writeheader()
        tulis.writerows(baris)


def muat_pemetaan(kb, path_penyakit=PEMETAAN_PENYAKIT, path_gejala=PEMETAAN_GEJALA):
    """Baca tabel pemetaan dan pastikan semua kode yang dipakai ada di basis pengetahuan."""
    penyakit = {}
    for b in baca_csv(path_penyakit):
        kode = b["kode"].strip()
        label = b["label_sumber"].strip().lower()
        if kode and kode != "-" and kode not in kb["penyakit"]:
            raise ValueError(f"pemetaan/penyakit.csv: kode {kode} tidak ada di basis pengetahuan")
        if label in penyakit and penyakit[label]["kode"] != kode:
            raise ValueError(f"pemetaan/penyakit.csv: label '{b['label_sumber']}' dipetakan ke dua kode berbeda")
        penyakit[label] = {"kode": kode, "catatan": b["catatan"]}

    gejala = []
    for b in baca_csv(path_gejala):
        kode = b["kode_gejala"].strip()
        if kode not in kb["gejala"]:
            raise ValueError(f"pemetaan/gejala.csv: kode {kode} tidak ada di basis pengetahuan")
        try:
            gejala.append((re.compile(b["pola"], re.I), kode))
        except re.error as e:
            raise ValueError(f"pemetaan/gejala.csv: pola '{b['pola']}' tidak valid ({e})") from None
    return penyakit, gejala


def gejala_tanpa_pola(kb, pola_gejala):
    """Gejala di basis pengetahuan yang belum punya pola di pemetaan/gejala.csv."""
    ada = {kode for _, kode in pola_gejala}
    return [k for k in kb["gejala"] if k not in ada]


def cari_gejala(teks, pola_gejala):
    """Cari kode gejala yang disebut di teks. Mengembalikan {kode: frasa_yang_cocok}."""
    ketemu = {}
    for pola, kode in pola_gejala:
        for m in pola.finditer(teks):
            if PENYANGKAL.search(teks[:m.start()]):
                continue  # "no spots" bukan gejala
            ketemu.setdefault(kode, m.group(0))
            break
    return dict(sorted(ketemu.items()))


def praproses(path_mentah=MENTAH, path_bersih=BERSIH, path_ditolak=DITOLAK, kb=None):
    """Saring data mentah menjadi kasus uji. Mengembalikan (kasus, ditolak)."""
    kb = kb or muat_kb()
    peta_penyakit, pola_gejala = muat_pemetaan(kb)
    mentah = baca_csv(path_mentah)

    ada = set(mentah[0]) if mentah else set()
    hilang = [v for k, v in KOLOM.items() if mentah and k not in KOLOM_OPSIONAL and v not in ada]
    if hilang:
        raise ValueError(f"Kolom wajib tidak ada di data mentah: {', '.join(hilang)}")

    def ambil(b, kunci):
        return (b.get(KOLOM[kunci]) or "").strip()

    kasus = {}     # (kode_penyakit, gejala) -> kasus, supaya deskripsi kembar jadi satu
    ditolak = []

    def tolak(b, alasan):
        ditolak.append({"id": ambil(b, "id"), "penyakit": ambil(b, "penyakit"), "alasan": alasan})

    for b in mentah:
        label = ambil(b, "penyakit")
        teks = ambil(b, "teks")

        if KOLOM["kategori"] in ada and ambil(b, "kategori") not in KATEGORI_DIPAKAI:
            tolak(b, f"kategori '{ambil(b, 'kategori')}' bukan identifikasi penyakit")
            continue
        if not label or not teks:
            tolak(b, "label penyakit atau teks deskripsi kosong")
            continue
        peta = peta_penyakit.get(label.lower())
        if peta is None:
            tolak(b, "label belum ada di pemetaan/penyakit.csv")
            continue
        if not peta["kode"]:
            tolak(b, f"luar cakupan basis pengetahuan ({peta['catatan']})")
            continue

        gejala = cari_gejala(teks, pola_gejala)
        if peta["kode"] != "-" and not gejala:
            tolak(b, "tidak ada gejala di teks yang cocok dengan pemetaan/gejala.csv")
            continue
        if peta["kode"] == "-" and gejala:
            tolak(b, f"label sehat tetapi teks menyebut gejala {', '.join(gejala)}; periksa data atau pola")
            continue

        kunci = (peta["kode"], tuple(gejala))
        if kunci in kasus:
            kasus[kunci]["sumber"] += f"; {ambil(b, 'id')}"
            continue
        kasus[kunci] = {
            "gejala": "; ".join(f"{g}={CF_LITERATUR:g}" for g in gejala),
            "diagnosis_pakar": peta["kode"],
            "sumber": ambil(b, "id"),
            "catatan": f"{label}. " + ("; ".join(f"'{f}' -> {g}" for g, f in gejala.items())
                                       or "tanpa gejala"),
            "_asal": ambil(b, "sumber") or "tidak disebutkan",
        }

    hasil = []
    for i, k in enumerate(kasus.values(), 1):
        k["catatan"] += f". Sumber: {k.pop('_asal')}"
        hasil.append({"kode": f"{AWALAN_KODE}{i:02d}", **k})

    tulis_csv(path_bersih, KOLOM_BERSIH, hasil)
    tulis_csv(path_ditolak, KOLOM_DITOLAK, ditolak)
    return hasil, ditolak


def cetak(hasil, ditolak, path_bersih=BERSIH, path_ditolak=DITOLAK):
    print(f"Kasus siap pakai: {len(hasil)}")
    for k in hasil:
        print(f"  {k['kode']}  {k['diagnosis_pakar']:3}  {k['gejala'] or '(tanpa gejala)':22}  dari {k['sumber']}")
    print(f"\nBaris ditolak: {len(ditolak)}")
    for d in ditolak:
        print(f"  {d['id']:13} {d['penyakit']:26} {d['alasan']}")
    kb = muat_kb()
    belum = gejala_tanpa_pola(kb, muat_pemetaan(kb)[1])
    if belum:
        print(f"\nPeringatan: gejala tanpa pola di pemetaan/gejala.csv, tidak akan terbaca dari teks: "
              f"{', '.join(belum)}")
    print(f"\nDitulis ke {path_bersih}\n       dan {path_ditolak}")


if __name__ == "__main__":
    args = sys.argv[1:3]
    hasil, ditolak = praproses(*args)
    cetak(hasil, ditolak, *(args[1:2] or [BERSIH]))
