# Spec Delta

## Purpose

Mengukur mutu materi ajar secara otomatis dan deterministik, melaporkan skornya
kepada manusia, dan memungkinkan dua versi prompt atau kode dibandingkan secara
adil lewat uji asap yang dapat diulang.

## ADDED Requirements

### Requirement: Pemeriksaan deterministik per pertemuan
Sistem SHALL memeriksa tiap pertemuan tanpa memanggil model, dan MUST
melaporkan tiap pemeriksaan sebagai lulus atau gagal beserta buktinya.

#### Scenario: Capaian tidak disebut di modul
- **WHEN** satu kode capaian pertemuan di `KURIKULUM.md` tidak muncul di `MODUL.md` pertemuan itu
- **THEN** pemeriksaan "capaian tertutup" gagal dan menyebut kode capaian yang hilang

#### Scenario: Soal tanpa tanda capaian
- **WHEN** satu butir soal di `LATIHAN.md` tidak memuat tanda capaian seperti `(P2-1)`
- **THEN** pemeriksaan "soal bertanda capaian" gagal dan menyebut nomor soalnya

#### Scenario: Capaian tidak diuji
- **WHEN** satu kode capaian pertemuan tidak diuji butir soal mana pun
- **THEN** pemeriksaan "capaian teruji" gagal dan menyebut kode capaiannya

#### Scenario: Lembar latihan membocorkan jawaban
- **WHEN** `LATIHAN.md` memuat penanda jawaban seperti "Jawaban:" atau "Kunci:"
- **THEN** pemeriksaan "latihan bebas jawaban" gagal dan menyebut barisnya

#### Scenario: Alokasi waktu tidak sama dengan durasi
- **WHEN** jumlah menit segmen satu pertemuan di `BLUEPRINT.md` berbeda dari durasinya
- **THEN** pemeriksaan "alokasi waktu" gagal dan menyebut kedua angkanya

#### Scenario: Solusi lab gagal dijalankan ulang
- **WHEN** pertemuan berlab dan solusi di `lab/solusi/` gagal saat dijalankan ulang oleh pemeriksa
- **THEN** pemeriksaan "lab jalan" gagal dan menyertakan potongan galatnya

#### Scenario: Pemeriksaan tidak berlaku
- **WHEN** sebuah pemeriksaan tidak berlaku untuk pertemuan itu, misalnya pertemuan tanpa lab
- **THEN** pemeriksaan dilaporkan sebagai "tidak berlaku" dan tidak dihitung dalam skor

### Requirement: Skor dan laporan pemeriksaan
Sistem SHALL menghitung skor tiap pertemuan sebagai persentase pemeriksaan yang
lulus dari yang berlaku, menulis laporannya ke `docs/PEMERIKSAAN.md`, dan
menampilkan ringkasannya di gate telaah.

#### Scenario: Laporan setelah produksi
- **WHEN** produksi pertemuan selesai
- **THEN** `docs/PEMERIKSAAN.md` memuat skor per pertemuan, skor rata-rata, dan daftar pemeriksaan yang gagal

#### Scenario: Pemeriksaan gagal masuk daftar perbaikan
- **WHEN** sebuah pemeriksaan gagal
- **THEN** kegagalannya masuk `docs/PERBAIKAN.md` sebagai butir berkeparahan tinggi dengan berkas sasarannya

### Requirement: Uji asap yang dapat diulang
Sistem SHALL menyediakan uji asap yang menjalankan pipeline penuh dengan jawaban
gate yang dipatok dan model yang dapat dipilih, tanpa mengubah konfigurasi
produksi.

#### Scenario: Dua versi dibandingkan
- **WHEN** uji asap dijalankan dua kali pada silabus dan model yang sama dengan versi prompt berbeda
- **THEN** kedua run menerima jawaban gate yang sama sehingga skor pemeriksaannya dapat dibandingkan langsung

#### Scenario: Kuota habis saat uji
- **WHEN** kuota penyedia habis selama uji asap
- **THEN** uji berhenti alih-alih menunggu reset kuota

#### Scenario: Nama proyek uji sudah dipakai
- **WHEN** uji asap dijalankan dengan nama proyek yang sudah pernah dijalankan
- **THEN** uji menolak jalan supaya hasil dua run tidak tercampur
