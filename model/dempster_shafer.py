"""Dempster-Shafer (DS) sebagai metode pembanding Certainty Factor.

Memakai basis_pengetahuan.json yang sama, tanpa data baru. Masukan dan bentuk keluaran
diagnosis_ds() sama persis dengan inferensi.diagnosis(), ditambah satu kunci opsional
"himpunan_terkuat". Web cukup mengganti nama fungsi untuk berpindah metode.

Alur (spesifikasi: docs/specification.md bagian A2):
1. fungsi_massa      : setiap gejala menjadi satu fungsi massa m
2. kombinasi_dempster: semua m digabung satu per satu, konflik K dinormalisasi
3. betp              : massa akhir diubah menjadi skor per penyakit (pignistic probability)

Istilah:
- Θ (theta)       : himpunan semua penyakit (P01..P09), artinya "belum tahu yang mana"
- himpunan fokus  : himpunan penyakit yang mendapat massa, misalnya {P05,P06,P07}
- K               : massa yang jatuh ke irisan kosong (bukti saling bertentangan)

Jalankan `python dempster_shafer.py` untuk mode tanya-jawab di terminal.
"""

import time

from inferensi import angka, buat_keluaran, muat_kb, periksa_masukan, susun_hasil, teks_fakta_awal


def teks_himpunan(himpunan, theta):
    """Tulis himpunan untuk jejak: "Θ", "∅", atau "{P01,P03}"."""
    if himpunan == theta:
        return "Θ"
    if not himpunan:
        return "∅"
    return "{" + ",".join(sorted(himpunan)) + "}"


def teks_massa(m, theta):
    """Tulis seluruh fungsi massa untuk jejak, Θ di akhir.

    Contoh: "m{P01} = 0.64, mΘ = 0.36"
    """
    urut = sorted(m.items(), key=lambda x: (x[0] == theta, -x[1], sorted(x[0])))
    return ", ".join(f"m{teks_himpunan(a, theta)} = {angka(v)}" for a, v in urut)


def fungsi_massa(fakta, kb):
    """Ubah setiap gejala yang dipilih menjadi fungsi massa.

    Untuk gejala g dengan CF pengguna u:
    - Aturan positif satu premis: semua penyakit yang disimpulkan g membentuk S_g.
      m(S_g) = CF pakar x u, sisanya ke Θ. Kalau CF pakar berbeda antarpenyakit di S_g,
      dipakai nilai maksimum dan dicatat.
    - Aturan negatif (R05, R09): m(Θ tanpa p) = |CF pakar| x u, sisanya ke Θ.
    - Aturan dengan lebih dari satu premis (R27) dan fakta antara diabaikan.

    Parameter:
        fakta: {kode_gejala: cf_pengguna}, hasil periksa_masukan().

    Mengembalikan:
        (daftar_massa, aturan_dipakai, catatan)
        - daftar_massa  : [(kode_gejala, teks_rumus, {frozenset(penyakit): massa}), ...]
        - aturan_dipakai: kode aturan yang menyumbang massa
        - catatan       : pesan untuk jejak (CF pakar yang berbeda di S_g)
    """
    theta = frozenset(kb["penyakit"])
    daftar, dipakai, catatan = [], [], []

    for g, u in fakta.items():
        tunggal = [r for r in kb["aturan"] if r["jika"] == [g] and r["maka"] in theta]
        positif = [r for r in tunggal if r["cf"] > 0]
        negatif = [r for r in tunggal if r["cf"] < 0]

        if positif:
            s_g = frozenset(r["maka"] for r in positif)
            nilai_pakar = sorted({r["cf"] for r in positif})
            cf_pakar = nilai_pakar[-1]
            if len(nilai_pakar) > 1:
                catatan.append(
                    f"Catatan {g}: CF pakar berbeda di {teks_himpunan(s_g, theta)} "
                    f"({', '.join(angka(v) for v in nilai_pakar)}), dipakai maksimum {angka(cf_pakar)}"
                )
            d = cf_pakar * u
            daftar.append((g, f"{angka(cf_pakar)} x {angka(u)}", {s_g: d, theta: 1 - d}))
            dipakai += [r["kode"] for r in positif]

        for r in negatif:
            d = abs(r["cf"]) * u
            rumus = f"|{angka(r['cf'])}| x {angka(u)} untuk bukan {r['maka']}"
            daftar.append((g, rumus, {theta - {r["maka"]}: d, theta: 1 - d}))
            dipakai.append(r["kode"])

    # buang massa nol, misalnya m(Θ) = 0 saat CF pakar dan CF pengguna sama-sama 1
    daftar = [(g, rumus, {a: v for a, v in m.items() if v > 0}) for g, rumus, m in daftar]
    return daftar, dipakai, catatan


def kombinasi_dempster(m1, m2):
    """Gabungkan dua fungsi massa dengan aturan kombinasi Dempster.

    Setiap pasangan himpunan fokus (A dari m1, B dari m2) menyumbang m1(A) x m2(B) ke irisan A∩B.
    Sumbangan ke irisan kosong dijumlah sebagai konflik K, lalu semua massa dibagi (1 - K).

    Mengembalikan:
        (massa_gabungan, K). Kalau K = 1 (konflik total), massa_gabungan = {}.
    """
    hasil = {}
    k = 0.0
    for a, va in m1.items():
        for b, vb in m2.items():
            irisan = a & b
            if irisan:
                hasil[irisan] = hasil.get(irisan, 0.0) + va * vb
            else:
                k += va * vb
    if k >= 1 - 1e-12:
        return {}, 1.0
    return {a: v / (1 - k) for a, v in hasil.items()}, k


def betp(m, theta):
    """Pignistic probability: BetP(p) = jumlah m(A) / |A| untuk setiap himpunan fokus A yang memuat p.

    Massa sebuah himpunan dibagi rata ke anggotanya. Total BetP semua penyakit = 1.
    """
    skor = {p: 0.0 for p in theta}
    for a, v in m.items():
        for p in a:
            skor[p] += v / len(a)
    return skor


def himpunan_terkuat(m, theta):
    """Himpunan fokus dengan massa terbesar, selain Θ (Θ hanya dipilih kalau tidak ada yang lain).

    Kalau massanya sama, dipilih himpunan yang lebih kecil (lebih spesifik).

    Mengembalikan:
        {"anggota": ["P05", "P06", "P07"], "massa": 0.8128}
    """
    pilihan = {a: v for a, v in m.items() if a != theta} or m
    terkuat = max(pilihan, key=lambda a: (pilihan[a], -len(a)))
    return {"anggota": sorted(terkuat), "massa": round(pilihan[terkuat], 4)}


def diagnosis_ds(input_pengguna, kb=None):
    """Diagnosis penyakit dengan Dempster-Shafer.

    Masukan, error, dan bentuk keluaran sama dengan inferensi.diagnosis(), dengan perbedaan:
    - "cf" dan "persen" berisi BetP, bukan CF;
    - "fakta_antara" selalu [] (R27 tidak dipakai);
    - ada kunci tambahan "himpunan_terkuat" kalau ada hasil.

    Kalau tidak ada gejala, tidak ada aturan yang cocok, atau terjadi konflik total (K = 1),
    "hasil" berisi [] dan alasannya ditulis di "jejak".
    """
    mulai = time.perf_counter()
    kb = kb or muat_kb()
    fakta = periksa_masukan(input_pengguna, kb)
    theta = frozenset(kb["penyakit"])
    jejak = [teks_fakta_awal(fakta)]

    if not fakta:
        return buat_keluaran([], [], jejak, [], mulai)

    jejak.append("Θ = " + teks_himpunan(theta, frozenset()))
    daftar, dipakai, catatan = fungsi_massa(fakta, kb)
    jejak += catatan
    if not daftar:
        jejak.append("Tidak ada aturan satu premis yang terpenuhi")
        return buat_keluaran([], [], jejak, [], mulai)

    for i, (g, rumus, m) in enumerate(daftar, 1):
        jejak.append(f"[m{i}] {g}: d = {rumus} | {teks_massa(m, theta)}")

    m = daftar[0][2]
    for i, (_, _, m_baru) in enumerate(daftar[1:], 2):
        m, k = kombinasi_dempster(m, m_baru)
        if not m:
            jejak.append(f"Kombinasi dengan m{i}: K = 1, konflik total. "
                         "Bukti saling bertentangan, tidak ada kesimpulan.")
            return buat_keluaran([], [], jejak, dipakai, mulai)
        jejak.append(f"Kombinasi dengan m{i}: K = {angka(k)} | {teks_massa(m, theta)}")

    hasil = susun_hasil({p: v for p, v in betp(m, theta).items() if v > 0}, kb)
    jejak.append("BetP(p) = jumlah m(A)/|A| untuk setiap himpunan fokus A yang memuat p")
    for h in hasil:
        jejak.append(f"Hasil {h['kode']} {h['nama']}: BetP = {angka(h['cf'])} ({h['persen']}%)")

    return buat_keluaran(hasil, [], jejak, dipakai, mulai, himpunan_terkuat=himpunan_terkuat(m, theta))


if __name__ == "__main__":
    from terminal import tanya_jawab

    tanya_jawab(diagnosis_ds)
