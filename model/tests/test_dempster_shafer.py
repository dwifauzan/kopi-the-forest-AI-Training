"""Uji Dempster-Shafer. Angka harapan dihitung manual (lihat komentar)."""

import unittest

from sistem_pakar import diagnosis, diagnosis_ds, muat_kb
from sistem_pakar.dempster_shafer import fungsi_massa, kombinasi_dempster

KB = muat_kb()
THETA = frozenset(KB["penyakit"])


def cari(out, kode):
    return next((h for h in out["hasil"] if h["kode"] == kode), None)


class TestDempsterShafer(unittest.TestCase):
    def test_satu_gejala(self):
        # m{P01} = 0.8 x 0.8 = 0.64, m(Θ) = 0.36
        # BetP(P01) = 0.64 + 0.36/9 = 0.68
        out = diagnosis_ds({"G01": 0.8}, KB)
        self.assertEqual(out["hasil"][0]["kode"], "P01")
        self.assertAlmostEqual(out["hasil"][0]["cf"], 0.68)
        self.assertEqual(out["hasil"][0]["persen"], 68.0)
        self.assertEqual(out["himpunan_terkuat"], {"anggota": ["P01"], "massa": 0.64})

    def test_gejala_jamur_akar(self):
        # m1{P05,P06,P07} = 0.6 x 0.8 = 0.48; m2{P05,P06,P07} = 0.8 x 0.8 = 0.64
        # gabung: 1 - 0.52 x 0.36 = 0.8128, m(Θ) = 0.1872, K = 0
        # BetP(P05) = 0.8128/3 + 0.1872/9 = 0.29173
        out = diagnosis_ds({"G12": 0.8, "G13": 0.8}, KB)
        self.assertAlmostEqual(cari(out, "P05")["cf"], 0.2917)
        self.assertEqual(out["himpunan_terkuat"], {"anggota": ["P05", "P06", "P07"], "massa": 0.8128})
        self.assertEqual(out["fakta_antara"], [])
        self.assertNotIn("R27", out["aturan_jalan"])

    def test_masukan_kosong(self):
        self.assertEqual(diagnosis_ds({}, KB)["hasil"], [])
        self.assertEqual(diagnosis_ds({"G01": 0.0}, KB)["hasil"], [])

    def test_konflik_dinormalisasi(self):
        # G01 pasti: m{P01} = 0.8, m(Θ) = 0.2; G17 pasti: m{P08} = 1.0
        # K = 0.8 x 1.0 = 0.8; m{P08} = 0.2 / (1 - 0.8) = 1
        daftar, _, _ = fungsi_massa({"G01": 1.0, "G17": 1.0}, KB)
        m, k = kombinasi_dempster(daftar[0][2], daftar[1][2])
        self.assertAlmostEqual(k, 0.8)
        self.assertGreater(k, 0)
        self.assertAlmostEqual(sum(m.values()), 1.0)
        self.assertAlmostEqual(m[frozenset({"P08"})], 1.0)
        out = diagnosis_ds({"G01": 1.0, "G17": 1.0}, KB)
        self.assertEqual(out["hasil"][0]["kode"], "P08")
        self.assertIn("K = 0.8", "\n".join(out["jejak"]))

    def test_konflik_total(self):
        # Tidak ada dua gejala di KB yang memberi massa 1 pada himpunan berbeda,
        # jadi massa dibangun langsung: m1{P08} = 1, m2{P01} = 1 -> K = 1
        m, k = kombinasi_dempster({frozenset({"P08"}): 1.0}, {frozenset({"P01"}): 1.0})
        self.assertEqual((m, k), ({}, 1.0))

    def test_aturan_negatif(self):
        # R09: m(Θ \ {P03}) = 0.6 x 1.0 = 0.6, m(Θ) = 0.4
        # BetP(P03) = 0.4/9 = 0.0444; penyakit lain = 0.6/8 + 0.4/9 = 0.1194
        out = diagnosis_ds({"G08": 1.0}, KB)
        self.assertAlmostEqual(cari(out, "P03")["cf"], 0.0444)
        self.assertAlmostEqual(cari(out, "P01")["cf"], 0.1194)
        self.assertFalse(any(h["tampil"] for h in out["hasil"]))

    def test_bentuk_sama_dengan_cf(self):
        masukan = {"G01": 0.8, "G02": 0.6, "G03": 0.4}
        a, b = diagnosis(masukan, KB), diagnosis_ds(masukan, KB)
        self.assertTrue(set(a) <= set(b))
        self.assertEqual(set(a["hasil"][0]), set(b["hasil"][0]))
        self.assertEqual(b["hasil"][0]["kode"], "P01")
        self.assertAlmostEqual(sum(h["cf"] for h in b["hasil"]), 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
