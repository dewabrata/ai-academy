# Spec Delta

## Purpose

Menerima silabus pelatihan dari berbagai format berkas maupun masukan langsung,
menormalkannya menjadi satu teks yang bisa dibaca peran AI, dan menyiapkan
ruang kerja proyek tempat seluruh materi disimpan.

## ADDED Requirements

### Requirement: Membaca silabus dari berkas multi-format
Sistem SHALL menerima silabus berupa berkas `.md`, `.txt`, `.docx`, atau `.pdf`,
dan MUST menormalkannya menjadi satu teks polos sebelum tahap mana pun berjalan.

#### Scenario: Silabus Markdown atau teks
- **WHEN** pengguna menunjuk berkas `.md` atau `.txt`
- **THEN** sistem membaca isinya apa adanya sebagai teks silabus

#### Scenario: Silabus Word
- **WHEN** pengguna menunjuk berkas `.docx`
- **THEN** sistem mengekstrak seluruh paragraf dan isi tabel, mempertahankan
  urutan kemunculan, menjadi teks silabus

#### Scenario: Silabus PDF
- **WHEN** pengguna menunjuk berkas `.pdf`
- **THEN** sistem mengekstrak teks tiap halaman berurutan menjadi teks silabus

#### Scenario: Format tidak didukung
- **WHEN** pengguna menunjuk berkas dengan ekstensi selain yang didukung
- **THEN** sistem berhenti sebelum tahap pertama dan menyebut format apa saja
  yang didukung

#### Scenario: Ekstraksi menghasilkan teks kosong
- **WHEN** berkas terbaca tetapi teks hasil ekstraksi kosong atau hanya spasi
  (misalnya PDF hasil pindai tanpa lapisan teks)
- **THEN** sistem berhenti dan memberi tahu pengguna bahwa berkas perlu
  dikonversi lebih dulu, alih-alih menjalankan pipeline dengan masukan kosong

### Requirement: Menerima silabus sebagai masukan langsung
Sistem SHALL menerima teks silabus yang diketik langsung sebagai argumen
perintah, tanpa memerlukan berkas.

#### Scenario: Silabus diketik di terminal
- **WHEN** pengguna menjalankan pipeline dengan teks silabus sebagai argumen
- **THEN** teks itu dipakai sebagai silabus dan disimpan ke ruang kerja proyek
  sebagai berkas sumber

### Requirement: Menyiapkan ruang kerja proyek
Sistem SHALL menyiapkan satu direktori proyek per silabus, dan MUST menyimpan
silabus asli beserta teks hasil normalisasi di dalamnya sebagai jejak sumber.

#### Scenario: Proyek baru
- **WHEN** pipeline dijalankan untuk silabus yang belum punya proyek
- **THEN** sistem membuat direktori proyek bernama turunan judul silabus,
  berisi subdirektori untuk dokumen perencanaan, materi per pertemuan, dan
  berkas sumber

#### Scenario: Nama proyek ditentukan pengguna
- **WHEN** pengguna menyebut nama proyek secara eksplisit
- **THEN** sistem memakai nama itu, dan jika direktorinya sudah ada, melanjutkan
  proyek tersebut alih-alih menimpanya

### Requirement: Melanjutkan proyek yang sudah ada
Sistem SHALL dapat melanjutkan proyek dari tahap tertentu tanpa mengulang
tahap yang dokumennya sudah ada.

#### Scenario: Melanjutkan dari tahap tertentu
- **WHEN** pengguna melanjutkan proyek dan menyebut tahap awal
- **THEN** sistem memulai dari tahap itu, memakai dokumen tahap sebelumnya yang
  sudah ada di ruang kerja
