"""API HTTP (JSON) untuk frontend. Hanya memakai pustaka standar Python (WSGI), tanpa Flask.

Endpoint (detail dan contoh: docs/api.md):
    GET  /api/status      server hidup + ringkasan basis pengetahuan
    GET  /api/gejala      data form: gejala per bagian + skala keyakinan
    GET  /api/penyakit    daftar penyakit beserta penyebab dan penanganan
    GET  /api/metode      metode yang tersedia ("cf", "ds")
    POST /api/diagnosis   {"gejala": {"G01": 0.8}, "metode": "cf"} -> keluaran diagnosis()
    POST /api/bandingkan  {"gejala": {"G01": 0.8}}                 -> {"cf": ..., "ds": ...}

Error selalu {"error": "pesan"} dengan status 400 (masukan salah), 404, 405, 413, atau 500.

Menjalankan:
    python main.py api [--host 127.0.0.1] [--port 5001]     # lokal
    gunicorn antarmuka.api:app                               # server produksi (dari folder model/)
    PythonAnywhere: di file WSGI, `from antarmuka.api import app as application`

CORS hanya perlu kalau browser memanggil API langsung (fetch dari JavaScript). Kalau Laravel
memanggil dari server (Http::post), CORS tidak perlu. Aktifkan dengan variabel lingkungan
API_CORS_ORIGIN, misalnya API_CORS_ORIGIN=http://localhost:8000.

Basis pengetahuan dibaca sekali saat server mulai. Setelah basis_pengetahuan.json diubah,
jalankan ulang server.
"""

import json
import os
import traceback
from wsgiref.simple_server import make_server

from sistem_pakar import METODE, daftar_pertanyaan, muat_kb

BATAS_BODY = 64 * 1024   # byte; masukan diagnosis normal jauh di bawah ini

STATUS_HTTP = {200: "200 OK", 204: "204 No Content", 400: "400 Bad Request", 404: "404 Not Found",
               405: "405 Method Not Allowed", 413: "413 Payload Too Large",
               500: "500 Internal Server Error"}


class ErrorApi(Exception):
    """Error yang dikirim ke klien apa adanya, dengan status HTTP tertentu."""

    def __init__(self, status, pesan):
        super().__init__(pesan)
        self.status = status


# ---------------------------------------------------------------------------
# Isi respons
# ---------------------------------------------------------------------------

def data_gejala(kb):
    """Data untuk menyusun form: gejala per bagian (urutan sama dengan mode terminal) dan skala."""
    return {
        "bagian": [{"nama": bagian, "gejala": [{"kode": k, "nama": n} for k, n in daftar]}
                   for bagian, daftar in daftar_pertanyaan(kb)],
        "skala": [{"label": s["label"], "nilai": s["nilai"]} for s in kb["skala_cf_pengguna"]],
        "nilai_bawaan": 0.0,
    }


def data_penyakit(kb):
    """Daftar penyakit: kode, nama, penyebab, dan solusi."""
    return [{"kode": k, "nama": p["nama"], "penyebab": p["penyebab"], "solusi": p["solusi"]}
            for k, p in kb["penyakit"].items()]


def ambil_gejala(body):
    """Ambil {kode_gejala: cf} dari body. Gejala bernilai 0 ("Tidak tahu") boleh ikut dikirim.

    Error:
        ErrorApi 400 kalau "gejala" bukan objek, atau semua gejala bernilai 0.
    """
    gejala = body.get("gejala")
    if not isinstance(gejala, dict):
        raise ErrorApi(400, 'Kolom "gejala" wajib berupa objek, contoh: {"gejala": {"G01": 0.8}}')
    try:
        ada = any(float(v) > 0 for v in gejala.values())
    except (TypeError, ValueError):
        ada = True   # biarkan periksa_masukan() memberi pesan yang menyebut kode gejalanya
    if not ada:
        raise ErrorApi(400, "Semua gejala 'Tidak tahu'. Pilih minimal satu gejala.")
    return gejala


def jalankan_metode(kode_metode, gejala, kb):
    """Jalankan satu metode. Error masukan dari sistem pakar diubah menjadi ErrorApi 400."""
    if kode_metode not in METODE:
        raise ErrorApi(400, f"Metode tidak dikenal: {kode_metode}. Pilihan: {', '.join(METODE)}")
    try:
        return {"metode": kode_metode, **METODE[kode_metode][1](gejala, kb)}
    except ValueError as e:
        raise ErrorApi(400, str(e)) from None


# ---------------------------------------------------------------------------
# WSGI
# ---------------------------------------------------------------------------

def baca_json(environ):
    """Baca body permintaan sebagai objek JSON.

    Error:
        ErrorApi 413 kalau body melebihi BATAS_BODY, 400 kalau bukan objek JSON.
    """
    try:
        panjang = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        panjang = 0
    if panjang > BATAS_BODY:
        raise ErrorApi(413, f"Body terlalu besar (maksimal {BATAS_BODY // 1024} KB)")
    try:
        body = json.loads(environ["wsgi.input"].read(panjang) or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ErrorApi(400, "Body harus JSON yang valid") from None
    if not isinstance(body, dict):
        raise ErrorApi(400, "Body harus berupa objek JSON")
    return body


def buat_app(kb=None):
    """Buat aplikasi WSGI. kb kosong = dibaca dari basis_pengetahuan.json sekali saja."""
    kb = kb or muat_kb()
    cors = os.environ.get("API_CORS_ORIGIN", "").strip()

    rute = {
        ("GET", "/api/status"): lambda body: {
            "status": "ok", "penyakit": len(kb["penyakit"]), "gejala": len(kb["gejala"]),
            "aturan": len(kb["aturan"])},
        ("GET", "/api/gejala"): lambda body: data_gejala(kb),
        ("GET", "/api/penyakit"): lambda body: data_penyakit(kb),
        ("GET", "/api/metode"): lambda body: [{"kode": k, "nama": nama} for k, (nama, _) in METODE.items()],
        ("POST", "/api/diagnosis"): lambda body: jalankan_metode(
            str(body.get("metode") or "cf").lower(), ambil_gejala(body), kb),
        ("POST", "/api/bandingkan"): lambda body: {
            k: jalankan_metode(k, ambil_gejala(body), kb) for k in METODE},
    }

    def app(environ, start_response):
        """Terima satu permintaan HTTP, kirim respons JSON."""
        metode = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/").rstrip("/") or "/"
        header = [("Content-Type", "application/json; charset=utf-8")]
        if cors:
            header += [("Access-Control-Allow-Origin", cors),
                       ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                       ("Access-Control-Allow-Headers", "Content-Type")]

        try:
            if metode == "OPTIONS":
                status, isi = 204, None
            elif (metode, path) in rute:
                body = baca_json(environ) if metode == "POST" else {}
                status, isi = 200, rute[(metode, path)](body)
            elif any(p == path for _, p in rute):
                raise ErrorApi(405, f"Metode {metode} tidak didukung untuk {path}")
            else:
                raise ErrorApi(404, f"Endpoint tidak ditemukan: {path}")
        except ErrorApi as e:
            status, isi = e.status, {"error": str(e)}
        except Exception:
            traceback.print_exc()   # detail hanya di log server, tidak dikirim ke klien
            status, isi = 500, {"error": "Terjadi kesalahan di server"}

        data = b"" if isi is None else json.dumps(isi, ensure_ascii=False).encode("utf-8")
        start_response(STATUS_HTTP[status], header + [("Content-Length", str(len(data)))])
        return [data]

    return app


def jalankan_server(host="127.0.0.1", port=5001):
    """Jalankan server pengembangan (satu permintaan sekaligus; cukup untuk lokal dan demo)."""
    with make_server(host, port, buat_app()) as server:
        print(f"API sistem pakar berjalan di http://{host}:{port}/api/status  (Ctrl+C untuk berhenti)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer dihentikan.")


# Objek WSGI untuk gunicorn / PythonAnywhere.
app = buat_app()
