
@extends('layout')

@section('title', 'Hasil Diagnosis | Kopi The Forest')

@section('content')

<div class="container">

    <div class="page-head">
        <div class="eyebrow">Hasil konsultasi</div>
        <h1>Hasil Diagnosis</h1>

        <p>
            Metode yang digunakan:
            <strong>
                {{ strtoupper($data['metode'] ?? '-') }}
            </strong>
        </p>
    </div>

    @php
        // Ambil daftar hasil diagnosis dari API Python
        // Hanya tampilkan penyakit dengan tampil = true
        $hasil = collect($data['hasil'] ?? [])
            ->filter(fn ($item) => !empty($item['tampil']))
            ->values();
    @endphp

    @if($hasil->isNotEmpty())

        @foreach($hasil as $item)

            <div class="result">

                <div class="result-top">

                    <div>
                        <div class="eyebrow">
                            Kemungkinan penyakit
                        </div>

                        <h2 style="font:700 25px 'Playfair Display'; margin:8px 0">
                            {{ $item['nama'] ?? $item['kode'] ?? 'Hasil diagnosis' }}
                        </h2>

                        <small>
                            Kode penyakit: {{ $item['kode'] ?? '-' }}
                        </small>
                    </div>

                    <div class="percent">
                        {{ number_format((float) ($item['persen'] ?? 0), 2) }}%
                    </div>

                </div>

                @if(!empty($item['solusi']))
                    <div class="alert">
                        <strong>Saran penanganan</strong>
                        <br>
                        {{ $item['solusi'] }}
                    </div>
                @endif

            </div>

        @endforeach

    @else

        <div class="alert">
            <strong>Belum ditemukan hasil diagnosis.</strong>

            <p>
                Gejala yang dipilih belum menghasilkan penyakit
                yang memenuhi ambang tampil pada sistem pakar.
            </p>

            <p>
                Silakan periksa kembali gejala tanaman dan
                tingkat keyakinan yang dipilih.
            </p>
        </div>

    @endif

    @if(!empty($data['fakta_antara']))

        <div class="panel">
            <h2>Saran pemeriksaan tambahan</h2>

            <pre style="white-space:pre-wrap">{{ json_encode(
                $data['fakta_antara'],
                JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE
            ) }}</pre>
        </div>

    @endif

    <div style="display:flex; gap:12px; flex-wrap:wrap; margin:28px 0">

        <a class="btn" href="{{ route('diagnosis.form') }}">
            Diagnosis Ulang
        </a>

        <a class="btn btn-outline" href="{{ route('history') }}">
            Lihat Riwayat
        </a>

    </div>

    <p class="muted">
        Hasil ini merupakan diagnosis awal berdasarkan basis
        pengetahuan sistem, bukan pengganti pemeriksaan langsung
        oleh ahli tanaman.
    </p>

</div>

@endsection
