"""Uji mesin Forward Chaining + CF. Angka harapan dihitung manual (lihat komentar)."""

import unittest

from inferensi import diagnosis, gabung_cf, muat_kb

KB = muat_kb()


def cari(out, kode):
    return next((h for h in out["hasil"] if h["kode"] == kode), None)


class TestBasisPengetahuan(unittest.TestCase):
    def test_isi_kb(self):
        self.assertEqual(len(KB["penyakit"]), 9)
        self.assertEqual(len(KB["gejala"]), 21)
        self.assertEqual(len(KB["aturan"]), 27)
        semua = set(KB["gejala"]) | set(KB["penyakit"]) | set(KB["fakta_antara"])
        for r in KB["aturan"]:
            for p in r["jika"]:
                self.assertIn(p, semua, r["kode"])
            self.assertIn(r["maka"], semua, r["kode"])
            self.assertIn(r["status"], ("sumber", "usulan", "divalidasi"))


class TestRumusCF(unittest.TestCase):
    def test_gabung_keduanya_positif(self):
        # 0.64 + 0.36 x (1 - 0.64) = 0.7696
        self.assertAlmostEqual(gabung_cf(0.64, 0.36), 0.7696)

    def test_gabung_keduanya_negatif(self):
        # -0.4 + (-0.6) x (1 + (-0.4)) = -0.76
        self.assertAlmostEqual(gabung_cf(-0.4, -0.6), -0.76)

    def test_gabung_beda_tanda(self):
        # (0.8 + (-0.32)) / (1 - 0.32) = 0.48 / 0.68 = 0.70588
        self.assertAlmostEqual(gabung_cf(0.8, -0.32), 0.48 / 0.68)


class TestDiagnosis(unittest.TestCase):
    def test_contoh_karat_daun(self):
        # R01: 0.8 x 0.8 = 0.64
        # R02: 0.6 x 0.6 = 0.36 -> 0.64 + 0.36 x 0.36 = 0.7696
        # R03: 0.4 x 0.4 = 0.16 -> 0.7696 + 0.16 x 0.2304 = 0.806464
        # R07: 0.6 x 0.6 = 0.36 (nematoda)
        out = diagnosis({"G01": 0.8, "G02": 0.6, "G03": 0.4}, KB)
        teratas = out["hasil"][0]
        self.assertEqual(teratas["kode"], "P01")
        self.assertEqual(teratas["persen"], 80.65)
        self.assertEqual(cari(out, "P03")["persen"], 36.0)
        self.assertEqual(out["aturan_jalan"], ["R01", "R02", "R03", "R07"])

    def test_satu_gejala(self):
        # R01: 0.8 x 0.8 = 0.64
        out = diagnosis({"G01": 0.8}, KB)
        self.assertEqual(len(out["hasil"]), 1)
        self.assertEqual(out["hasil"][0]["cf"], 0.64)
        self.assertTrue(out["hasil"][0]["tampil"])

    def test_cf_negatif_bercak_daun(self):
        # R04: 1.0 x 0.8 = 0.8; R05: 0.8 x -0.4 = -0.32
        # (0.8 - 0.32) / (1 - 0.32) = 0.7059 -> 70.59%
        out = diagnosis({"G04": 1.0, "G05": 0.8}, KB)
        self.assertEqual(cari(out, "P02")["persen"], 70.59)

    def test_hanya_g08_tidak_ada_yang_tampil(self):
        # R09: 1.0 x -0.6 = -0.6, nematoda tetap ada di hasil tapi tidak tampil
        out = diagnosis({"G08": 1.0}, KB)
        p03 = cari(out, "P03")
        self.assertEqual(p03["cf"], -0.6)
        self.assertFalse(any(h["tampil"] for h in out["hasil"]))

    def test_masukan_kosong_dan_tidak_tahu(self):
        self.assertEqual(diagnosis({}, KB)["hasil"], [])
        self.assertEqual(diagnosis({"G01": 0.0}, KB)["hasil"], [])

    def test_fakta_antara_saran_periksa_akar(self):
        # P05/P06/P07: 0.48 + 0.64 x 0.52 = 0.8128 (seri)
        # R27: min(0.8, 0.8) x 0.8 = 0.64
        out = diagnosis({"G12": 0.8, "G13": 0.8}, KB)
        nilai = {h["kode"]: h["cf"] for h in out["hasil"]}
        self.assertEqual(nilai, {"P05": 0.8128, "P06": 0.8128, "P07": 0.8128})
        self.assertEqual(len(out["fakta_antara"]), 1)
        self.assertEqual(out["fakta_antara"][0]["kode"], "F01")
        self.assertEqual(out["fakta_antara"][0]["cf"], 0.64)
        self.assertIn("R27", out["aturan_jalan"])

    def test_premis_dan_memakai_min(self):
        # R27: min(0.4, 1.0) x 0.8 = 0.32
        out = diagnosis({"G12": 0.4, "G13": 1.0}, KB)
        self.assertEqual(out["fakta_antara"][0]["cf"], 0.32)
        self.assertIn("min(0.4, 1)", "\n".join(out["jejak"]))

    def test_jamur_akar_putih_teratas(self):
        # P07: 0.8128 + 0.64 x (1 - 0.8128) = 0.932608
        out = diagnosis({"G12": 0.8, "G13": 0.8, "G16": 0.8}, KB)
        self.assertEqual(out["hasil"][0]["kode"], "P07")
        self.assertEqual(out["hasil"][0]["cf"], 0.9326)

    def test_bentuk_keluaran_dan_validasi(self):
        out = diagnosis({"G02": 0.6, "G01": 0.8}, KB)
        self.assertEqual(set(out), {"hasil", "fakta_antara", "jejak", "aturan_jalan", "waktu_ms"})
        self.assertEqual(set(out["hasil"][0]), {"kode", "nama", "cf", "persen", "solusi", "tampil"})
        cfs = [h["cf"] for h in out["hasil"]]
        self.assertEqual(cfs, sorted(cfs, reverse=True))
        self.assertTrue(out["jejak"][0].startswith("Fakta awal:"))
        self.assertIsInstance(out["waktu_ms"], float)
        with self.assertRaises(ValueError):
            diagnosis({"G99": 0.8}, KB)
        with self.assertRaises(ValueError):
            diagnosis({"G01": 1.5}, KB)


if __name__ == "__main__":
    unittest.main()
