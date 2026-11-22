"""Dempster-Shafer sebagai pembanding Certainty Factor.

Memakai basis_pengetahuan.json yang sama, tanpa data baru. Bentuk keluaran
diagnosis_ds() sama dengan inferensi.diagnosis(), ditambah kunci opsional
"himpunan_terkuat". Spesifikasi: docs/specification.md bagian A2.
"""

import time

from inferensi import angka, muat_kb, periksa_masukan, susun_hasil


def teks_himpunan(himpunan, theta):
    if himpunan == theta:
        return "Θ"
    if himpunan == frozenset():
        return "∅"
    return "{" + ",".join(sorted(himpunan)) + "}"


def teks_massa(m, theta):
    urut = sorted(m.items(), key=lambda x: (x[0] == theta, -x[1], sorted(x[0])))
    return ", ".join(f"m{teks_himpunan(a, theta)} = {angka(v)}" for a, v in urut)


def fungsi_massa(fakta, kb):
    """Bangun fungsi massa dari setiap gejala.

    Mengembalikan (daftar_massa, aturan_dipakai, catatan). Setiap massa adalah
    dict {frozenset(penyakit): nilai}. Aturan dengan lebih dari satu premis
    (R27) dan fakta antara diabaikan.
    """
    theta = frozenset(kb["penyakit"])
    daftar = []
    dipakai = []
    catatan = []

    for g, u in fakta.items():
        tunggal = [r for r in kb["aturan"] if r["jika"] == [g] and r["maka"] in theta]
        positif = [r for r in tunggal if r["cf"] > 0]
        negatif = [r for r in tunggal if r["cf"] < 0]

        if positif:
            s_g = frozenset(r["maka"] for r in positif)
            nilai_pakar = {r["cf"] for r in positif}
            cf_pakar = max(nilai_pakar)
            if len(nilai_pakar) > 1:
                catatan.append(
                    f"Catatan {g}: CF pakar berbeda di {teks_himpunan(s_g, theta)} "
                    f"({', '.join(angka(v) for v in sorted(nilai_pakar))}), dipakai maksimum {angka(cf_pakar)}"
                )
            d = cf_pakar * u
            daftar.append((g, f"{angka(cf_pakar)} x {angka(u)}", {s_g: d, theta: 1 - d}))
            dipakai += [r["kode"] for r in positif]

        for r in negatif:
            bukan_p = theta - {r["maka"]}
            d = abs(r["cf"]) * u
            daftar.append((g, f"|{angka(r['cf'])}| x {angka(u)} untuk bukan {r['maka']}", {bukan_p: d, theta: 1 - d}))
            dipakai.append(r["kode"])

    # buang massa nol (misalnya m(Θ) = 0 saat CF pakar dan pengguna sama-sama 1)
    daftar = [(g, rumus, {a: v for a, v in m.items() if v > 0}) for g, rumus, m in daftar]
    return daftar, dipakai, catatan


def kombinasi_dempster(m1, m2):
    """Aturan kombinasi Dempster. Mengembalikan (massa_gabungan, K).

    Kalau K = 1 (konflik total), massa_gabungan = {}.
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
    """Pignistic probability: BetP(p) = jumlah m(A)/|A| untuk setiap A yang memuat p."""
    skor = {p: 0.0 for p in theta}
    for a, v in m.items():
        for p in a:
            skor[p] += v / len(a)
    return skor


def diagnosis_ds(input_pengguna, kb=None):
    """Diagnosis dengan Dempster-Shafer. Masukan dan keluaran sama dengan diagnosis()."""
    mulai = time.perf_counter()
    kb = kb or muat_kb()
    fakta = periksa_masukan(input_pengguna, kb)
    theta = frozenset(kb["penyakit"])

    def selesai(hasil, jejak, aturan_jalan, terkuat=None):
        out = {
            "hasil": hasil,
            "fakta_antara": [],
            "jejak": jejak,
            "aturan_jalan": aturan_jalan,
            "waktu_ms": round((time.perf_counter() - mulai) * 1000, 3),
        }
        if terkuat is not None:
            out["himpunan_terkuat"] = terkuat
        return out

    if not fakta:
        return selesai([], ["Fakta awal: tidak ada gejala yang dipilih"], [])

    jejak = ["Fakta awal: " + ", ".join(f"{k} ({angka(v)})" for k, v in fakta.items())]
    jejak.append("Θ = {" + ",".join(sorted(theta)) + "}")
    daftar, dipakai, catatan = fungsi_massa(fakta, kb)
    jejak += catatan

    if not daftar:
        jejak.append("Tidak ada aturan satu premis yang terpenuhi")
        return selesai([], jejak, [])

    for i, (g, rumus, m) in enumerate(daftar, 1):
        jejak.append(f"[m{i}] {g}: d = {rumus} | {teks_massa(m, theta)}")

    m = daftar[0][2]
    for i, (_, _, m_baru) in enumerate(daftar[1:], 2):
        m, k = kombinasi_dempster(m, m_baru)
        if not m:
            jejak.append(f"Kombinasi dengan m{i}: K = 1, konflik total. Bukti saling bertentangan, tidak ada kesimpulan.")
            return selesai([], jejak, dipakai)
        jejak.append(f"Kombinasi dengan m{i}: K = {angka(k)} | {teks_massa(m, theta)}")

    skor = betp(m, theta)
    hasil = susun_hasil({p: v for p, v in skor.items() if v > 0}, kb)

    bukan_theta = {a: v for a, v in m.items() if a != theta}
    pilihan = bukan_theta or m
    a_terkuat = max(pilihan, key=lambda a: (pilihan[a], -len(a)))
    terkuat = {"anggota": sorted(a_terkuat), "massa": round(pilihan[a_terkuat], 4)}

    jejak.append("BetP(p) = jumlah m(A)/|A| untuk setiap himpunan fokus A yang memuat p")
    for h in hasil:
        jejak.append(f"Hasil {h['kode']} {h['nama']}: BetP = {angka(h['cf'])} ({h['persen']}%)")

    return selesai(hasil, jejak, dipakai, terkuat)


if __name__ == "__main__":
    from inferensi import tanya_jawab

    tanya_jawab(diagnosis_ds)
