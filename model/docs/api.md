# API Sistem Pakar (untuk frontend)

API JSON di `model/antarmuka/api.py`. Hanya memakai pustaka standar Python, jadi tidak perlu `pip install`.

## Menjalankan

```bash
cd model
python3 main.py api                    # http://127.0.0.1:5001
python3 main.py api --port 5002        # port lain
python3 main.py api --host 0.0.0.0     # bisa diakses dari HP/laptop lain di jaringan yang sama
```

Cek: buka `http://127.0.0.1:5001/api/status` di browser.

- Port bawaan 5001, karena 5000 sering dipakai AirPlay di macOS.
- Basis pengetahuan dibaca sekali saat server mulai. Setelah `basis_pengetahuan.json` diubah, jalankan ulang server.
- Server bawaan melayani satu permintaan pada satu waktu. Ini cukup untuk lokal dan demo, karena satu diagnosis kurang dari 1 ms. Untuk produksi, lihat bagian Deploy.

## Endpoint

Semua respons berupa JSON UTF-8. Kalau terjadi error, bentuknya selalu `{"error": "pesan berbahasa Indonesia"}`. Pesan ini boleh langsung ditampilkan ke pengguna.

| Metode | Path | Body | Respons |
|---|---|---|---|
| GET | `/api/status` | - | `{"status": "ok", "penyakit": 9, "gejala": 21, "aturan": 27}` |
| GET | `/api/gejala` | - | Data form: gejala per bagian + skala |
| GET | `/api/penyakit` | - | `[{"kode", "nama", "penyebab", "solusi"}, ...]` |
| GET | `/api/metode` | - | `[{"kode": "cf", "nama": "Certainty Factor"}, {"kode": "ds", ...}]` |
| POST | `/api/diagnosis` | `{"gejala": {...}, "metode": "cf"}` | Hasil diagnosis + `"metode"` |
| POST | `/api/bandingkan` | `{"gejala": {...}}` | `{"cf": hasil, "ds": hasil}` |

| Status | Arti |
|---|---|
| 200 | Berhasil |
| 400 | Masukan salah: body bukan JSON, `gejala` bukan objek, kode gejala tidak dikenal, nilai bukan angka 0–1, semua gejala "Tidak tahu", atau metode tidak dikenal |
| 404 / 405 | Path salah / metode HTTP salah |
| 413 | Body lebih dari 64 KB |
| 500 | Error di server (detailnya hanya ada di log server) |

### `GET /api/gejala`: untuk menyusun form

```json
{
  "bagian": [
    {"nama": "Daun", "gejala": [{"kode": "G01", "nama": "Daun timbul bercak kuning, lalu berubah coklat"}, ...]},
    {"nama": "Tajuk", "gejala": [...]}
  ],
  "skala": [{"label": "Tidak tahu", "nilai": 0.0}, {"label": "Mungkin", "nilai": 0.4}, ...],
  "nilai_bawaan": 0.0
}
```

Pakai data ini untuk membuat form. **Jangan menyalin daftar gejala ke HTML atau kode Laravel**, sesuai aturan spesifikasi bahwa basis pengetahuan hanya ada di satu tempat. Urutan bagian dan gejala sudah sama dengan mode terminal, dan otomatis ikut berubah kalau basis pengetahuan berubah.

### `POST /api/diagnosis`

Body:
```json
{"gejala": {"G01": 0.8, "G02": "0.6", "G03": 0}, "metode": "cf"}
```
- Nilai boleh angka atau teks angka (nilai dari form HTML berupa teks). Gejala bernilai 0 ("Tidak tahu") boleh ikut dikirim dan akan diabaikan.
- `metode` bisa `"cf"` (bawaan) atau `"ds"`.

Respons (bentuknya sama dengan kontrak `diagnosis()` di `docs/specification.md` bagian 4):
```json
{
  "metode": "cf",
  "hasil": [
    {"kode": "P01", "nama": "Karat daun kopi", "cf": 0.8065, "persen": 80.65, "solusi": "...", "tampil": true},
    {"kode": "P03", "nama": "Nematoda", "cf": 0.36, "persen": 36.0, "solusi": "...", "tampil": true}
  ],
  "fakta_antara": [],
  "jejak": ["Fakta awal: G01 (0.8), G02 (0.6), G03 (0.4)", "[1] R01: JIKA G01 MAKA P01 | CF = 0.8 x 0.8 = 0.64", "..."],
  "aturan_jalan": ["R01", "R02", "R03", "R07"],
  "waktu_ms": 0.05
}
```

Cara menampilkan (spesifikasi B3):
- **Kartu utama:** `hasil[0]` kalau `tampil` bernilai `true`. Tampilkan nama, `persen`, progress bar, dan `solusi`.
- **Penyakit lain:** item `hasil` lain yang `tampil` bernilai `true`. Item dengan `tampil: false` (termasuk CF negatif) jangan ditampilkan.
- **Tidak ada yang tampil:** "Gejala belum cukup untuk menyimpulkan penyakit. Tambah gejala atau hubungi penyuluh."
- **`fakta_antara` tidak kosong:** tampilkan kotak peringatan berisi `saran`.
- **"Lihat langkah perhitungan":** isi dengan `jejak`, satu baris per item.
- **`waktu_ms`:** tampilkan dengan huruf kecil.
- **Untuk DS**, ada kunci tambahan `himpunan_terkuat`. Isi `cf`/`persen` adalah nilai BetP, bukan CF, dan `fakta_antara` selalu kosong.

## Memanggil dari Laravel (`frontend/`)

Laravel memanggil API **dari server** dengan HTTP client bawaan, jadi tidak perlu CORS.

`.env`:
```
SISTEM_PAKAR_URL=http://127.0.0.1:5001
```

`config/services.php`:
```php
'sistem_pakar' => [
    'url' => env('SISTEM_PAKAR_URL', 'http://127.0.0.1:5001'),
],
```

Contoh controller:
```php
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;

class DiagnosisController extends Controller
{
    private function api()
    {
        return Http::baseUrl(config('services.sistem_pakar.url'))->acceptJson()->timeout(5);
    }

    public function form()
    {
        $form = $this->api()->get('/api/gejala')->throw()->json();
        return view('diagnosis.form', ['form' => $form]);
    }

    public function proses(Request $request)
    {
        try {
            $res = $this->api()->post('/api/diagnosis', [
                'gejala' => $request->input('gejala', []),      // dari <input name="gejala[G01]">
                'metode' => $request->input('metode', 'cf'),
            ]);
        } catch (ConnectionException $e) {
            return back()->withErrors(['api' => 'Server sistem pakar tidak dapat dihubungi.']);
        }

        if ($res->status() === 400) {
            return back()->withInput()->withErrors(['gejala' => $res->json('error')]);
        }
        return view('diagnosis.hasil', ['out' => $res->throw()->json()]);
    }
}
```

Potongan Blade untuk form (radio, bukan slider, sesuai spesifikasi B2):
```blade
@foreach ($form['bagian'] as $bagian)
  <h5>{{ $bagian['nama'] }}</h5>
  @foreach ($bagian['gejala'] as $g)
    <p>{{ $g['nama'] }}</p>
    @foreach ($form['skala'] as $s)
      <label>
        <input type="radio" name="gejala[{{ $g['kode'] }}]" value="{{ $s['nilai'] }}"
               @checked(old('gejala.'.$g['kode'], $form['nilai_bawaan']) == $s['nilai'])>
        {{ $s['label'] }}
      </label>
    @endforeach
  @endforeach
@endforeach
```

Kalau suatu saat browser memanggil API langsung, misalnya dengan `fetch()` dari JavaScript, jalankan server dengan `API_CORS_ORIGIN=http://localhost:8000 python3 main.py api` (isi dengan alamat Laravel).

## Contoh dengan curl

```bash
curl http://127.0.0.1:5001/api/gejala
curl -X POST http://127.0.0.1:5001/api/diagnosis -H 'Content-Type: application/json' \
     -d '{"gejala": {"G04": 1, "G05": 0.8}, "metode": "cf"}'          # P02 70.59%
curl -X POST http://127.0.0.1:5001/api/bandingkan -H 'Content-Type: application/json' \
     -d '{"gejala": {"G12": 0.8, "G13": 0.8, "G16": 0.8}}'
```

## Deploy

Objek WSGI-nya adalah `antarmuka.api:app`, dijalankan dari folder `model/`.

- **PythonAnywhere:** di file WSGI, tambahkan folder `model/` ke `sys.path`, lalu `from antarmuka.api import app as application`.
- **Render/VPS:** `pip install gunicorn`, lalu `gunicorn --chdir model -w 2 -b 0.0.0.0:$PORT antarmuka.api:app`.

Laravel dan API boleh berada di server yang berbeda. Cukup isi `SISTEM_PAKAR_URL` dengan alamat API.
