"""Uji praproses. Harapan diambil dari isi data/mentah/leafnet_coffee_kb.csv (12 baris)."""

import os
import tempfile
import unittest

from inferensi import muat_kb
from praproses import cari_gejala, muat_pemetaan, praproses

KB = muat_kb()


class TestPraproses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        bersih = os.path.join(cls.tmp.name, "bersih.csv")
        ditolak = os.path.join(cls.tmp.name, "ditolak.csv")
        cls.hasil, cls.ditolak = praproses(path_bersih=bersih, path_ditolak=ditolak, kb=KB)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_kasus_yang_lolos(self):
        # Rust (kb_1, kb_2 kembar), Cercospora (kb_5, kb_6 kembar), Healthy (kb_11)
        ringkas = [(k["diagnosis_pakar"], k["gejala"], k["sumber"]) for k in self.hasil]
        self.assertEqual(ringkas, [
            ("P01", "G01=1; G02=1; G03=1", "coffee_kb_1; coffee_kb_2"),
            ("P02", "G04=1", "coffee_kb_5; coffee_kb_6"),
            ("-", "", "coffee_kb_11"),
        ])
        self.assertEqual([k["kode"] for k in self.hasil], ["L01", "L02", "L03"])

    def test_baris_yang_ditolak(self):
        # Leaf miner x2, Phoma x2, Red spider mite, Berry blotch: luar cakupan; General: kategori lain
        self.assertEqual(len(self.ditolak), 7)
        self.assertEqual(len(self.hasil) + len(self.ditolak) + 2, 12)  # 2 baris kembar digabung
        luar = {d["penyakit"] for d in self.ditolak if d["alasan"].startswith("luar cakupan")}
        self.assertEqual(luar, {"Leaf miner", "Phoma", "Red spider mite", "Berry blotch"})

    def test_hasil_bisa_dibaca_mesin_inferensi(self):
        from evaluasi import urai_gejala
        for k in self.hasil:
            self.assertTrue(set(urai_gejala(k["gejala"])) <= set(KB["gejala"]))

    def test_kolom_opsional_dan_label_sehat_bergejala(self):
        # Data lain tanpa kolom category/source tetap bisa diproses
        mentah = os.path.join(self.tmp.name, "lain.csv")
        with open(mentah, "w", encoding="utf-8") as f:
            f.write("id,disease,answer\n"
                    "a1,Rust,Leaves show defoliation and bare branches.\n"
                    "a2,Healthy,Leaves show defoliation.\n")
        hasil, ditolak = praproses(mentah, os.path.join(self.tmp.name, "b.csv"),
                                   os.path.join(self.tmp.name, "d.csv"), kb=KB)
        self.assertEqual([(k["diagnosis_pakar"], k["gejala"]) for k in hasil], [("P01", "G02=1; G03=1")])
        self.assertIn("label sehat", ditolak[0]["alasan"])

    def test_kolom_wajib_hilang(self):
        mentah = os.path.join(self.tmp.name, "rusak.csv")
        with open(mentah, "w", encoding="utf-8") as f:
            f.write("id,label\nx,Rust\n")
        with self.assertRaisesRegex(ValueError, "disease"):
            praproses(mentah, os.path.join(self.tmp.name, "b.csv"), os.path.join(self.tmp.name, "d.csv"), kb=KB)

    def test_penyangkalan_dan_lesi_coklat(self):
        _, pola = muat_pemetaan(KB)
        # "no spots" pada daun sehat bukan gejala
        self.assertEqual(cari_gejala("Healthy leaves have no yellow spots turning brown.", pola), {})
        # "brown lesions" (karat) tidak boleh terbaca sebagai G05 yang ber-CF negatif untuk P02
        self.assertNotIn("G05", cari_gejala("spots merging into larger brown lesions", pola))


if __name__ == "__main__":
    unittest.main()
