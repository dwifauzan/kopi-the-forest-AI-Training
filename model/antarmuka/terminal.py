"""Tampilan terminal: tanya-jawab gejala dan cetak hasil diagnosis.

Dipisah dari paket sistem_pakar supaya mesin inferensi tidak berisi print/input.
Web tidak memakai modul ini; web cukup memanggil sistem_pakar.diagnosis() atau
sistem_pakar.diagnosis_ds().
"""

from sistem_pakar import daftar_pertanyaan, muat_kb


def pilihan_bawaan(kb):
    """Indeks pilihan skala yang bernilai 0 ("Tidak tahu"). Dipakai saat pengguna menekan Enter.

    Dicari berdasarkan nilainya, bukan posisinya, jadi tetap benar kalau urutan skala berubah.
    """
    return next((i for i, s in enumerate(kb["skala_cf_pengguna"]) if s["nilai"] == 0), 0)


def kumpulkan_jawaban(kb):
    """Tanyakan setiap gejala di terminal, dikelompokkan per bagian tanaman.

    Pertanyaan diambil dari daftar_pertanyaan(kb). Pengguna menjawab dengan nomor skala;
    Enter = "Tidak tahu". Kalau input habis (EOF), gejala sisanya dianggap "Tidak tahu".

    Mengembalikan:
        {kode_gejala: cf_pengguna}, hanya gejala yang CF-nya > 0.
    """
    skala = kb["skala_cf_pengguna"]
    bawaan = pilihan_bawaan(kb)
    label_bawaan = skala[bawaan]["label"]

    print("=== Sistem Pakar Diagnosis Penyakit Tanaman Kopi ===")
    print("Pilih tingkat keyakinan untuk setiap gejala:")
    for i, s in enumerate(skala):
        print(f"  {i} = {s['label']}")
    print(f"Tekan Enter untuk '{label_bawaan}'.\n")

    jawaban = {}
    for bagian, daftar in daftar_pertanyaan(kb):
        print(f"--- {bagian} ---")
        for kode, nama in daftar:
            pilihan = tanya_satu(f"{kode} {nama}? ", len(skala), bawaan)
            if pilihan is None:
                print(f"\nMasukan berakhir, gejala sisanya dianggap '{label_bawaan}'.")
                return jawaban
            if skala[pilihan]["nilai"] > 0:
                jawaban[kode] = skala[pilihan]["nilai"]
    return jawaban


def tanya_satu(pertanyaan, jumlah_pilihan, bawaan):
    """Tanya satu gejala sampai jawabannya valid.

    Mengembalikan:
        indeks pilihan (int), atau None kalau input habis (EOF).
    """
    while True:
        try:
            isi = input(pertanyaan).strip()
        except EOFError:
            return None
        if isi == "":
            return bawaan
        if isi.isdigit() and int(isi) < jumlah_pilihan:
            return int(isi)
        print(f"  Masukkan angka 0-{jumlah_pilihan - 1}.")


def tampilkan_hasil(out, judul="Hasil diagnosis"):
    """Cetak keluaran diagnosis() atau diagnosis_ds() ke terminal.

    Urutannya sama dengan halaman hasil di web: penyakit teratas beserta penanganan,
    penyakit lain yang tampil, saran fakta antara, langkah perhitungan, dan waktu proses.
    """
    tampil = [h for h in out["hasil"] if h["tampil"]]
    print(f"\n=== {judul} ===")
    if not tampil:
        print("Gejala belum cukup untuk menyimpulkan penyakit. Tambah gejala atau hubungi penyuluh.")
    for i, h in enumerate(tampil, 1):
        print(f"{i}. {h['nama']} ({h['kode']}): {h['persen']}%")
        if i == 1:
            print(f"   Penanganan: {h['solusi']}")
    for f in out["fakta_antara"]:
        print(f"\nPerhatian ({f['nama']}): {f['saran']}")
    print("\n--- Langkah perhitungan ---")
    for baris in out["jejak"]:
        print(baris)
    print(f"\nWaktu proses: {out['waktu_ms']} ms")
    print("Hasil ini diagnosis awal. Konfirmasikan ke penyuluh.")


def tanya_jawab(fungsi_diagnosis):
    """Alur lengkap mode terminal: tanya gejala, jalankan diagnosis, cetak hasil.

    Parameter:
        fungsi_diagnosis: sistem_pakar.diagnosis atau sistem_pakar.diagnosis_ds.
    """
    kb = muat_kb()
    jawaban = kumpulkan_jawaban(kb)
    if not jawaban:
        print("\nSemua gejala 'Tidak tahu'. Pilih minimal satu gejala.")
        return
    tampilkan_hasil(fungsi_diagnosis(jawaban, kb))
