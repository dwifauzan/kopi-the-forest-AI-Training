"""Uji evaluasi: diagnosis seri, ringkasan per sumber, dan pemeriksaan kasus."""

import contextlib
import io
import os
import tempfile
import unittest

from evaluasi import evaluasi, urai_gejala

KOLOM = "kode,gejala,diagnosis_pakar\n"


class TestEvaluasi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hasil = os.path.join(self.tmp.name, "hasil.csv")

    def tearDown(self):
        self.tmp.cleanup()

    def tulis(self, nama, isi):
        path = os.path.join(self.tmp.name, nama)
        with open(path, "w", encoding="utf-8") as f:
            f.write(KOLOM + isi)
        return path

    def jalankan(self, *path):
        keluar = io.StringIO()
        with contextlib.redirect_stdout(keluar):
            baris, ringkasan = evaluasi(list(path), self.hasil)
        return baris, ringkasan, keluar.getvalue()

    def test_seri_tidak_diputus_urut_abjad(self):
        # G12 + G13: P05, P06, P07 sama-sama 0.8128 -> tidak boleh dianggap P05
        path = self.tulis("pakar.csv", 'K01,"G12=0.8; G13=0.8",P05\n')
        baris, ringkasan, teks = self.jalankan(path)
        cf = baris[0]
        self.assertEqual(cf[2], "P05/P06/P07")
        self.assertEqual(cf[4], "FALSE")
        r = ringkasan[("CF", "pakar")]
        self.assertEqual((r["benar"], r["dilabel"], r["seri"]), (0, 1, 1))
        self.assertIn("seri", teks)

    def test_ringkasan_per_sumber(self):
        pakar = self.tulis("kasus_uji.csv", 'K01,"G01=0.8",P01\n')
        literatur = self.tulis("kasus_literatur.csv", 'L01,"G04=1",P02\nL02,,-\n')
        _, ringkasan, teks = self.jalankan(pakar, literatur)
        self.assertEqual(ringkasan[("CF", "kasus_uji")]["benar"], 1)
        self.assertEqual(ringkasan[("CF", "kasus_literatur")]["benar"], 2)
        self.assertEqual(ringkasan[("CF", "kasus_literatur")]["dilabel"], 2)
        self.assertIn("kesesuaian literatur", teks)

    def test_peringatan_kasus_ganda_dan_kode_asing(self):
        path = self.tulis("pakar.csv", 'K01,"G01=0.8",P01\nK01,"G04=1",Phoma\n')
        _, _, teks = self.jalankan(path)
        self.assertIn("K01 muncul lebih dari sekali", teks)
        self.assertIn("'PHOMA' tidak ada di basis pengetahuan", teks)

    def test_error_menyebut_kasus(self):
        path = self.tulis("pakar.csv", 'K07,"G01=abc",P01\n')
        with self.assertRaisesRegex(ValueError, "K07"):
            self.jalankan(path)

    def test_urai_gejala_desimal_koma(self):
        self.assertEqual(urai_gejala("G01=0,8; G02=0.6"), {"G01": 0.8, "G02": 0.6})
        self.assertEqual(urai_gejala("G01=0,8, G02=1"), {"G01": 0.8, "G02": 1.0})
        self.assertEqual(urai_gejala(""), {})


if __name__ == "__main__":
    unittest.main()
