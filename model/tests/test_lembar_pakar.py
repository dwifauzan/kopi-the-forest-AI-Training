"""Uji lembar kasus buta: lembar tidak membocorkan jawaban, dan impor ke kasus uji aman."""

import copy
import csv
import os
import tempfile
import unittest

from persiapan_data.berkas_csv import baca_csv
from persiapan_data.lembar_pakar import (KOLOM_KASUS, NAMA_KUNCI, NAMA_LEMBAR, buat_lembar,
                                         impor_lembar, susun_kasus)
from sistem_pakar import muat_kb

KB = muat_kb()


class TestLembarPakar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        self.lembar = os.path.join(self.folder, NAMA_LEMBAR)
        self.kasus = os.path.join(self.folder, "kasus_uji.csv")
        with open(self.kasus, "w", encoding="utf-8") as f:
            f.write(",".join(KOLOM_KASUS) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def isi_lembar(self, isian):
        """Tiru pakar: isi kolom lembar untuk kode tertentu. isian = {kode: {kolom: nilai}}."""
        baris = baca_csv(self.lembar)
        for b in baris:
            b.update(isian.get(b["kode"], {}))
        with open(self.lembar, "w", encoding="utf-8", newline="") as f:
            tulis = csv.DictWriter(f, fieldnames=list(baris[0]))
            tulis.writeheader()
            tulis.writerows(baris)

    def test_lembar_buta(self):
        kasus = buat_lembar(KB, self.folder)
        baris = baca_csv(self.lembar)
        self.assertEqual(len(baris), len(kasus))
        self.assertTrue(all(b["diagnosis_pakar"] == "" for b in baris))
        # asal kasus hanya ada di kunci internal, bukan di lembar pakar
        self.assertNotIn("jenis", baris[0])
        self.assertNotIn("dibentuk_dari", baris[0])
        self.assertTrue(os.path.exists(os.path.join(self.folder, NAMA_KUNCI)))

    def test_kasus_dari_basis_pengetahuan(self):
        kasus = susun_kasus(KB)
        asal = {k["dibentuk_dari"] for k in kasus if k["jenis"] == "khas"}
        self.assertEqual(asal, set(KB["penyakit"]))        # setiap penyakit punya kasus khas
        self.assertEqual({k["jenis"] for k in kasus},
                         {"khas", "sebagian", "lemah", "negatif", "gabungan", "campuran", "acak"})
        semua = [frozenset(k["gejala"].items()) for k in kasus]
        self.assertEqual(len(semua), len(set(semua)))       # tidak ada kasus kembar
        for k in kasus:
            self.assertTrue(set(k["gejala"]) <= set(KB["gejala"]))
            self.assertTrue(all(0 < v < 1 for v in k["gejala"].values()))

    def test_acakan_tetap(self):
        self.assertEqual(susun_kasus(KB), susun_kasus(KB))

    def test_ikut_berubah_kalau_kb_berubah(self):
        kb = copy.deepcopy(KB)
        kb["gejala"]["G22"] = {"nama": "Pucuk mengering", "bagian": "Pucuk"}
        kb["penyakit"]["P10"] = {"nama": "Penyakit uji", "penyebab": "-", "solusi": "-"}
        kb["aturan"].append({"kode": "R28", "jika": ["G22"], "maka": "P10", "cf": 0.6, "status": "usulan"})
        khas = [k for k in susun_kasus(kb) if k["jenis"] == "khas" and k["dibentuk_dari"] == "P10"]
        self.assertEqual(khas[0]["gejala"], {"G22": 0.8})

    def test_tidak_menimpa_lembar_yang_sudah_diisi(self):
        buat_lembar(KB, self.folder)
        self.isi_lembar({"K01": {"diagnosis_pakar": "P01"}})
        with self.assertRaises(FileExistsError):
            buat_lembar(KB, self.folder)
        buat_lembar(KB, self.folder, timpa=True)

    def test_impor(self):
        buat_lembar(KB, self.folder)
        self.isi_lembar({
            "K01": {"diagnosis_pakar": "p04", "nama_pakar": "Pakar Uji", "tanggal": "2026-11-26"},
            "K02": {"diagnosis_pakar": "-", "catatan": "perlu cek akar"},
        })
        ditambah, dilewati, peringatan = impor_lembar(self.lembar, self.kasus, KB)
        self.assertEqual(ditambah, ["K01", "K02"])
        self.assertEqual(peringatan, [])
        self.assertTrue(all(alasan == "diagnosis pakar belum diisi" for _, alasan in dilewati))

        hasil = {b["kode"]: b for b in baca_csv(self.kasus)}
        self.assertEqual(hasil["K01"]["diagnosis_pakar"], "P04")
        self.assertEqual(hasil["K02"]["nama_pakar"], "Pakar Uji")      # diisi dari baris pertama
        self.assertIn("perlu cek akar", hasil["K02"]["catatan"])

        # impor ulang tidak menggandakan kasus
        ditambah, dilewati, _ = impor_lembar(self.lembar, self.kasus, KB)
        self.assertEqual(ditambah, [])
        self.assertEqual(len(baca_csv(self.kasus)), 2)

    def test_impor_dari_excel_titik_koma(self):
        # Excel berbahasa Indonesia menyimpan CSV dengan pemisah ";" dan BOM
        buat_lembar(KB, self.folder)
        baris = baca_csv(self.lembar)
        baris[0]["diagnosis_pakar"] = "P01"
        with open(self.lembar, "w", encoding="utf-8-sig", newline="") as f:
            tulis = csv.DictWriter(f, fieldnames=list(baris[0]), delimiter=";", lineterminator="\r\n")
            tulis.writeheader()
            tulis.writerows(baris)
        ditambah, _, _ = impor_lembar(self.lembar, self.kasus, KB)
        self.assertEqual(ditambah, [baris[0]["kode"]])

    def test_impor_kolom_hilang_tidak_diam(self):
        with open(self.lembar, "w", encoding="utf-8") as f:
            f.write("Kode\tGejala\tDiagnosis\nK01\tG01=0.8\tP01\n")
        with self.assertRaisesRegex(ValueError, "kolom wajib tidak ada"):
            impor_lembar(self.lembar, self.kasus, KB)

    def test_impor_gejala_rusak(self):
        buat_lembar(KB, self.folder)
        self.isi_lembar({"K03": {"diagnosis_pakar": "P01", "gejala": "G99=0.8"}})
        with self.assertRaisesRegex(ValueError, "K03"):
            impor_lembar(self.lembar, self.kasus, KB)


if __name__ == "__main__":
    unittest.main()
