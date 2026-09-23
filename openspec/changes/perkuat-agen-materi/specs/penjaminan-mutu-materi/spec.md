# Spec Delta

## ADDED Requirements

### Requirement: Rubrik berskor dan vonis per pertemuan
Reviewer SHALL menilai tiap pertemuan pada rubrik berskor 1–4 untuk akurasi
teknis, ketertutupan capaian, keterbacaan terhadap level, dan koherensi, lalu
MUST memberi vonis per pertemuan berdasarkan ambang yang tertulis.

#### Scenario: Ada kesalahan teknis
- **WHEN** satu pertemuan memuat kesalahan teknis yang akan diajarkan sebagai kebenaran
- **THEN** skor akurasi pertemuan itu 1 dan vonisnya TOLAK, apa pun skor dimensi lain

#### Scenario: Semua dimensi memadai
- **WHEN** semua dimensi satu pertemuan berskor 3 atau lebih
- **THEN** vonisnya LULUS

#### Scenario: Ada dimensi lemah tanpa kesalahan teknis
- **WHEN** ada dimensi berskor 2 dan tidak ada yang berskor 1
- **THEN** vonisnya PERLU-REVISI

#### Scenario: Vonis tampil di gate
- **WHEN** gate telaah ditampilkan
- **THEN** jumlah pertemuan per vonis tampil bersama jumlah temuan
