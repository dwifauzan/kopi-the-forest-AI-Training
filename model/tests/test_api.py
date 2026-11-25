"""Uji API JSON (antarmuka/api.py) tanpa menjalankan server: aplikasi WSGI dipanggil langsung."""

import contextlib
import io
import json
import unittest
from unittest import mock
from wsgiref.util import setup_testing_defaults

from antarmuka.api import BATAS_BODY, buat_app
from sistem_pakar import muat_kb

KB = muat_kb()


class TestApi(unittest.TestCase):
    def setUp(self):
        self.app = buat_app(KB)

    def minta(self, metode, path, body=None, mentah=None, environ=None):
        """Kirim satu permintaan ke aplikasi. Mengembalikan (status_angka, json_atau_None, header)."""
        data = mentah if mentah is not None else (b"" if body is None else json.dumps(body).encode())
        env = {"REQUEST_METHOD": metode, "PATH_INFO": path, "CONTENT_LENGTH": str(len(data)),
               "wsgi.input": io.BytesIO(data), **(environ or {})}
        setup_testing_defaults(env)
        hasil = {}

        def start_response(status, header):
            hasil["status"], hasil["header"] = int(status.split()[0]), dict(header)

        isi = b"".join(self.app(env, start_response))
        return hasil["status"], json.loads(isi) if isi else None, hasil["header"]

    def test_gejala_untuk_form(self):
        status, isi, header = self.minta("GET", "/api/gejala")
        self.assertEqual(status, 200)
        self.assertEqual(header["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual([b["nama"] for b in isi["bagian"]], KB["urutan_bagian"])
        self.assertEqual(sum(len(b["gejala"]) for b in isi["bagian"]), 21)
        self.assertEqual(isi["skala"][0], {"label": "Tidak tahu", "nilai": 0.0})

    def test_diagnosis_cf_sama_dengan_kontrak(self):
        # angka sama dengan test_inferensi: karat daun 80.65%; nilai teks dari form juga diterima
        status, isi, _ = self.minta("POST", "/api/diagnosis",
                                    {"gejala": {"G01": "0.8", "G02": 0.6, "G03": 0.4, "G05": 0}})
        self.assertEqual(status, 200)
        self.assertEqual(isi["metode"], "cf")
        self.assertEqual(isi["hasil"][0]["kode"], "P01")
        self.assertEqual(isi["hasil"][0]["persen"], 80.65)
        self.assertEqual(set(isi) - {"metode"}, {"hasil", "fakta_antara", "jejak", "aturan_jalan", "waktu_ms"})

    def test_diagnosis_ds_dan_bandingkan(self):
        status, isi, _ = self.minta("POST", "/api/diagnosis", {"gejala": {"G12": 0.8}, "metode": "DS"})
        self.assertEqual((status, isi["metode"]), (200, "ds"))
        self.assertIn("himpunan_terkuat", isi)
        self.assertTrue(any("Θ" in baris for baris in isi["jejak"]))     # unicode utuh di JSON

        status, isi, _ = self.minta("POST", "/api/bandingkan", {"gejala": {"G12": 0.8, "G13": 0.8}})
        self.assertEqual(status, 200)
        self.assertEqual(set(isi), {"cf", "ds"})
        self.assertEqual(isi["cf"]["fakta_antara"][0]["kode"], "F01")

    def test_masukan_salah_400(self):
        kasus = [
            ({"gejala": {}}, "minimal satu gejala"),
            ({"gejala": {"G01": 0}}, "minimal satu gejala"),
            ({"gejala": [["G01", 0.8]]}, "wajib berupa objek"),
            ({"gejala": {"G99": 0.8}}, "tidak dikenal: G99"),
            ({"gejala": {"G01": "abc"}}, "harus angka"),
            ({"gejala": {"G01": True}}, "harus angka"),
            ({"gejala": {"G01": None}}, "harus angka"),
            ({"gejala": {"G01": 1.5}}, "di antara 0 dan 1"),
            ({"gejala": {"G01": -0.5}}, "di antara 0 dan 1"),
            ({"gejala": {"G01": 0.8}, "metode": "ml"}, "Metode tidak dikenal"),
        ]
        for body, pesan in kasus:
            status, isi, _ = self.minta("POST", "/api/diagnosis", body)
            self.assertEqual(status, 400, body)
            self.assertIn(pesan, isi["error"], body)

        self.assertEqual(self.minta("POST", "/api/diagnosis", mentah=b"{bukan json")[0], 400)
        self.assertEqual(self.minta("POST", "/api/diagnosis", mentah=b"[1, 2]")[0], 400)

    def test_status_http_lain(self):
        self.assertEqual(self.minta("GET", "/api/tidak-ada")[0], 404)
        self.assertEqual(self.minta("GET", "/api/diagnosis")[0], 405)
        self.assertEqual(self.minta("GET", "/api/status/")[0], 200)              # garis miring akhir boleh
        besar = b'{"gejala": {"G01": 0.8}, "x": "' + b"a" * BATAS_BODY + b'"}'
        self.assertEqual(self.minta("POST", "/api/diagnosis", mentah=besar)[0], 413)

    def test_error_server_tidak_membocorkan_detail(self):
        with mock.patch("antarmuka.api.data_penyakit", side_effect=KeyError("rahasia")), \
             contextlib.redirect_stderr(io.StringIO()):
            status, isi, _ = self.minta("GET", "/api/penyakit")
        self.assertEqual(status, 500)
        self.assertNotIn("rahasia", isi["error"])

    def test_cors_hanya_kalau_diaktifkan(self):
        self.assertNotIn("Access-Control-Allow-Origin", self.minta("GET", "/api/status")[2])
        with mock.patch.dict("os.environ", {"API_CORS_ORIGIN": "http://localhost:8000"}):
            self.app = buat_app(KB)
        status, isi, header = self.minta("OPTIONS", "/api/diagnosis")
        self.assertEqual((status, isi), (204, None))
        self.assertEqual(header["Access-Control-Allow-Origin"], "http://localhost:8000")


if __name__ == "__main__":
    unittest.main()
