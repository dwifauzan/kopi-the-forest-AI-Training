<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\View\View;

class DiagnosisController extends Controller
{
    private string $api = 'http://127.0.0.1:5001';

    public function index(): View
    {
        return view('home');
    }

    public function form(): View
    {
    $response = Http::timeout(5)->get($this->api . '/api/gejala');

    abort_unless(
        $response->successful(),
        503,
        'Layanan model Python belum berjalan.'
    );

    return view('diagnosis', [
        'data' => $response->json()
    ]);
    }

    public function diagnose(Request $request): View
    {
        $validated = $request->validate([
            'metode' => ['required', 'in:cf,ds'],
            'gejala' => ['required', 'array'],
            'gejala.*' => ['required', 'numeric', 'min:0', 'max:1'],
        ]);

        $response = Http::timeout(15)->post($this->api . '/api/diagnosis', $validated);
        if (!$response->successful()) {
            return view('diagnosis-error', ['message' => $response->json('error', 'Diagnosis gagal diproses.')]);
        }

        $hasil = $response->json();
        $history = session('riwayat_diagnosis', []);
        array_unshift($history, [
            'tanggal' => now()->format('d M Y H:i'),
            'metode' => $hasil['metode'],
            'hasil' => $hasil['hasil'] ?? [],
        ]);
        session(['riwayat_diagnosis' => array_slice($history, 0, 10)]);

        return view('hasil', ['data' => $hasil]);
    }

    public function history(): View
    {
        return view('riwayat', ['riwayat' => session('riwayat_diagnosis', [])]);
    }
}
