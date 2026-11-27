
@extends('layout')

@section('title', 'Diagnosis Tanaman Kopi | Kopi The Forest')

@section('content')

<div class="container">

    <div class="page-head">
        <div class="eyebrow">Konsultasi tanaman</div>

        <h1>Diagnosis Penyakit Kopi</h1>

        <p>
            Pilih tingkat keyakinan untuk setiap gejala.
            Pilih "Tidak tahu" jika gejala tidak terlihat
            atau kamu belum yakin.
        </p>
    </div>

    <form method="POST" action="{{ route('diagnosis.process') }}">
        @csrf

        {{-- Daftar gejala berdasarkan bagian tanaman --}}
        @foreach($data['bagian'] as $bagian)

            <div class="panel">

                <h2>{{ $bagian['nama'] }}</h2>

                @foreach($bagian['gejala'] as $gejala)

                    <div class="symptom">

                        <div>
                            <label for="{{ $gejala['kode'] }}">
                                {{ $gejala['nama'] }}
                            </label>

                            <small>
                                Kode gejala: {{ $gejala['kode'] }}
                            </small>
                        </div>

                        <select
                            id="{{ $gejala['kode'] }}"
                            name="gejala[{{ $gejala['kode'] }}]"
                            required
                        >

                            @foreach($data['skala'] as $skala)

                                <option
                                    value="{{ $skala['nilai'] }}"
                                    @selected(
                                        old(
                                            'gejala.'.$gejala['kode'],
                                            $data['nilai_bawaan']
                                        ) == $skala['nilai']
                                    )
                                >
                                    {{ $skala['label'] }}
                                </option>

                            @endforeach

                        </select>

                    </div>

                @endforeach

            </div>

        @endforeach

        {{-- Pilihan metode diagnosis --}}
        <div class="panel">

            <h2>Metode Diagnosis</h2>

            <div class="method-wrap">

                <label for="metode">Pilih metode:</label>

                <select
                    class="method"
                    style="max-width:300px"
                    id="metode"
                    name="metode"
                >

                    <option
                        value="cf"
                        @selected(old('metode', 'cf') == 'cf')
                    >
                        Certainty Factor
                    </option>

                    <option
                        value="ds"
                        @selected(old('metode') == 'ds')
                    >
                        Dempster-Shafer
                    </option>

                </select>

            </div>

            <p class="muted">
                Certainty Factor merupakan metode utama.
                Dempster-Shafer disediakan sebagai pembanding.
            </p>

            <button class="btn" type="submit">
                Proses Diagnosis →
            </button>

        </div>

    </form>

</div>

@endsection
