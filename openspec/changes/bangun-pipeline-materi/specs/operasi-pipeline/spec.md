# Spec Delta

## Purpose

Menjalankan pipeline produksi materi secara andal: mengorkestrasi tahap,
menangani kegagalan dan batas kuota tanpa kehilangan pekerjaan, mencatat event
untuk pemantauan, dan mencegah dua pipeline berjalan bersamaan di satu proyek.

## ADDED Requirements

### Requirement: Konteks tiap peran terpisah
Sistem SHALL menjalankan tiap tahap sebagai pemanggilan agent tersendiri dengan
system prompt perannya sendiri, sehingga konteks satu peran tidak tercampur
dengan peran lain.

#### Scenario: Peran membaca hasil peran sebelumnya
- **WHEN** sebuah peran memerlukan hasil peran sebelumnya
- **THEN** peran itu membacanya dari berkas di ruang kerja, bukan dari riwayat
  percakapan peran lain

### Requirement: Perilaku peran diatur lewat berkas prompt
Sistem SHALL menyimpan system prompt tiap peran sebagai berkas Markdown
terpisah, dan mengubah perilaku peran MUST tidak memerlukan perubahan kode.

#### Scenario: Standar materi berlaku ke semua peran
- **WHEN** standar materi bersama diubah di satu berkas
- **THEN** perubahan itu berlaku ke seluruh peran tanpa menyalinnya ke tiap
  berkas prompt

### Requirement: Kegagalan tahap ditawarkan diulang
Sistem SHALL melaporkan tahap yang gagal beserta alasannya dan menawarkan
mengulang tahap itu, tanpa mengulang tahap yang sudah berhasil.

#### Scenario: Tahap gagal
- **WHEN** sebuah tahap gagal
- **THEN** sistem menampilkan alasannya dan menawarkan mengulang tahap itu saja

#### Scenario: Pengguna tidak mengulang
- **WHEN** pengguna menolak mengulang tahap yang gagal
- **THEN** pipeline berhenti dan dokumen yang sudah ada tetap tersimpan

### Requirement: Batas kuota tidak menghilangkan pekerjaan
Sistem SHALL menangani batas kuota atau batas laju penyedia model dengan
menunggu sampai waktu reset lalu mengulang tahap itu, dan MUST menanyakan lebih
dulu bila waktu tunggunya melebihi ambang yang dikonfigurasi.

#### Scenario: Kuota habis dengan reset dekat
- **WHEN** kuota habis dan waktu resetnya di bawah ambang
- **THEN** sistem menunggu sampai reset lalu mengulang tahap itu otomatis

#### Scenario: Kuota habis dengan reset jauh
- **WHEN** waktu reset melebihi ambang yang dikonfigurasi
- **THEN** sistem bertanya lebih dulu alih-alih menunggu diam-diam

### Requirement: Pencatatan event
Sistem SHALL mencatat setiap mulai tahap, selesai tahap, gate, kegagalan, dan
batas kuota sebagai event terstruktur yang dapat dibaca ulang, memuat nama
tahap, model yang benar-benar dipakai, durasi, dan biaya.

#### Scenario: Riwayat proyek dibaca ulang
- **WHEN** pengguna memeriksa riwayat sebuah proyek
- **THEN** seluruh event tahap dapat dibaca berurutan beserta model, durasi, dan
  biayanya

### Requirement: Panel kendali web lokal
Sistem SHALL menyediakan panel kendali web untuk memantau status proyek,
menjalankan pipeline, dan menjawab gate, dan panel itu MUST hanya terikat ke
antarmuka lokal secara bawaan.

#### Scenario: Panel diakses secara lokal
- **WHEN** panel dijalankan dengan setelan bawaan
- **THEN** panel hanya dapat dibuka dari mesin yang sama

#### Scenario: Panel dibuka ke jaringan tanpa sandi
- **WHEN** panel dikonfigurasi terikat ke alamat non-lokal tanpa sandi diisi
- **THEN** panel MUST menolak berjalan, karena panel dapat menjalankan pipeline
  yang punya akses eksekusi perintah

### Requirement: Kunci satu-pipeline per proyek
Sistem SHALL mencegah dua pipeline berjalan bersamaan pada proyek yang sama.

#### Scenario: Pipeline kedua dijalankan
- **WHEN** pipeline dijalankan untuk proyek yang pipeline-nya masih berjalan
- **THEN** permintaan itu ditolak beserta keterangan proses yang sedang berjalan

#### Scenario: Kunci tertinggal dari proses yang mati
- **WHEN** kunci masih ada tetapi prosesnya sudah tidak hidup
- **THEN** kunci itu dianggap kedaluwarsa dan pipeline baru boleh berjalan

### Requirement: Perintah berbahaya ditolak untuk semua peran
Sistem SHALL menolak perintah shell yang merusak atau mengirim data keluar pada
semua peran, termasuk peran yang memang memerlukan eksekusi kode.

#### Scenario: Peran mencoba perintah terlarang
- **WHEN** sebuah peran mencoba menjalankan perintah pada daftar terlarang
- **THEN** perintah itu ditolak dan penolakannya tercatat sebagai event

### Requirement: Luaran biner dihasilkan lewat skrip
Sistem SHALL menghasilkan berkas DOCX dan PPTX lewat skrip Python dari sumber
Markdown, bukan ditulis langsung sebagai biner oleh peran AI.

#### Scenario: Sumber Markdown diubah
- **WHEN** sumber Markdown sebuah materi direvisi
- **THEN** berkas DOCX dan PPTX-nya dihasilkan ulang dari sumber itu, sehingga
  keduanya tidak pernah menyimpang dari sumbernya
