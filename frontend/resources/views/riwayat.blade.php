@extends('layout')
@section('title','Riwayat Diagnosis | Kopi The Forest')
@section('content')
<div class="container"><div class="page-head"><div class="eyebrow">Catatan konsultasi</div><h1>Riwayat Diagnosis</h1><p>Riwayat tersimpan pada sesi browser yang sedang digunakan.</p></div>
@if(count($riwayat))
@foreach($riwayat as $item)
<div class="result"><div class="result-top"><div><h2 style="font:700 21px 'Playfair Display';margin:0">{{ $item['metode'] }}</h2><p class="muted">{{ $item['tanggal'] }}</p></div><a class="btn btn-outline" href="{{ route('diagnosis.form') }}">Diagnosis Baru</a></div>
@forelse($item['hasil'] as $penyakit)<p><strong>{{ $penyakit['nama'] ?? $penyakit['kode'] ?? 'Penyakit' }}</strong> — {{ $penyakit['persen'] ?? $penyakit['persentase'] ?? 0 }}%</p>@empty<p class="muted">Tidak ada penyakit yang melewati ambang tampil.</p>@endforelse</div>
@endforeach
@else<div class="panel empty">Belum ada riwayat diagnosis.<br><br><a class="btn" href="{{ route('diagnosis.form') }}">Mulai Diagnosis</a></div>@endif</div>
@endsection
