"""Lokasi semua file data. Ubah di sini kalau struktur folder data/ berubah."""

import os

FOLDER_MODEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(FOLDER_MODEL, "data")

# Data literatur (praproses.py)
MENTAH = os.path.join(DATA, "mentah", "leafnet_coffee_kb.csv")
PEMETAAN_PENYAKIT = os.path.join(DATA, "pemetaan", "penyakit.csv")
PEMETAAN_GEJALA = os.path.join(DATA, "pemetaan", "gejala.csv")
KASUS_LITERATUR = os.path.join(DATA, "bersih", "kasus_literatur.csv")
DITOLAK = os.path.join(DATA, "bersih", "ditolak.csv")

# Data pakar (lembar_pakar.py)
KASUS_UJI = os.path.join(DATA, "kasus_uji.csv")
FOLDER_LEMBAR = os.path.join(DATA, "lembar_pakar")

# Keluaran evaluasi (selalu ditimpa)
HASIL_EVALUASI = os.path.join(DATA, "hasil_evaluasi.csv")
