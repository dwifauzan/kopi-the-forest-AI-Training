<?php

use App\Http\Controllers\DiagnosisController;
use Illuminate\Support\Facades\Route;

Route::get('/', [DiagnosisController::class, 'index'])->name('home');
Route::get('/diagnosis', [DiagnosisController::class, 'form'])->name('diagnosis.form');
Route::post('/diagnosis', [DiagnosisController::class, 'diagnose'])->name('diagnosis.process');
Route::get('/riwayat', [DiagnosisController::class, 'history'])->name('history');
