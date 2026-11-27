@extends('layout')
@section('title','Diagnosis Gagal')
@section('content')
<div class="container"><div class="page-head"><h1>Diagnosis belum dapat diproses</h1><div class="alert">{{ $message }}</div><a class="btn" href="{{ route('diagnosis.form') }}">Kembali ke Form Diagnosis</a></div></div>
@endsection
