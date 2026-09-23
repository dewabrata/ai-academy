# Spec Delta

## Purpose

Memproduksi materi ajar siap pakai untuk tiap pertemuan — modul bacaan, deck
presentasi, latihan berkunci, dan lab kode yang terbukti jalan — berdasarkan
blueprint yang sudah disetujui, dengan satu pertemuan pilot lebih dulu sebagai
contoh gaya.

## ADDED Requirements

### Requirement: Pertemuan pilot diproduksi dan disetujui lebih dulu
Sistem SHALL memproduksi seluruh luaran untuk satu pertemuan pilot, lalu MUST
meminta persetujuan pengguna atas pilot itu sebelum memproduksi pertemuan
lainnya.

#### Scenario: Pilot disetujui
- **WHEN** pengguna menyetujui pertemuan pilot
- **THEN** sistem memproduksi pertemuan sisanya memakai pilot itu sebagai acuan
  gaya, kedalaman, dan format

#### Scenario: Pilot diberi masukan
- **WHEN** pengguna memberi masukan atas pertemuan pilot
- **THEN** sistem merevisi pilot itu sesuai masukan, menyimpan masukan tersebut
  sebagai acuan gaya yang berlaku untuk semua pertemuan berikutnya, lalu
  bertanya lagi

#### Scenario: Pemilihan pertemuan pilot
- **WHEN** blueprint memuat lebih dari satu pertemuan
- **THEN** pertemuan pilot bawaannya adalah pertemuan pertama, dan pengguna
  SHALL dapat memilih pertemuan lain sebagai pilot

### Requirement: Modul bacaan per pertemuan
Sistem SHALL menghasilkan modul bacaan tiap pertemuan dalam Markdown dan DOCX,
memuat teori, contoh konkret, dan rangkuman, serta MUST menutup seluruh capaian
pembelajaran pertemuan itu.

#### Scenario: Modul lengkap
- **WHEN** satu pertemuan selesai diproduksi
- **THEN** modulnya memuat tiap capaian pertemuan itu, contoh untuk tiap konsep,
  dan rangkuman penutup

#### Scenario: Luaran DOCX
- **WHEN** modul Markdown selesai
- **THEN** sistem menghasilkan berkas DOCX berisi isi yang sama dengan hierarki
  judul yang terjaga, dan kegagalan konversi MUST dilaporkan sebagai kegagalan
  tahap, bukan diabaikan

### Requirement: Deck presentasi per pertemuan
Sistem SHALL menghasilkan deck presentasi PPTX tiap pertemuan yang mengikuti
alur segmen di blueprint, dan tiap slide MUST padat — bukan salinan paragraf
modul.

#### Scenario: Deck mengikuti alur sesi
- **WHEN** blueprint satu pertemuan memuat beberapa segmen
- **THEN** deck memuat slide pembuka berisi capaian, slide per segmen sesuai
  urutannya, dan slide penutup berisi rangkuman

#### Scenario: Slide terlalu padat teks
- **WHEN** sebuah slide akan memuat teks melebihi batas kepadatan yang
  ditetapkan standar materi
- **THEN** isinya dipecah ke beberapa slide atau diringkas menjadi butir

### Requirement: Latihan dengan kunci jawaban dan rubrik
Sistem SHALL menghasilkan latihan tiap pertemuan beserta kunci jawaban dan
rubrik penilaian, disimpan terpisah dari lembar latihan peserta.

#### Scenario: Latihan dan kunci terpisah
- **WHEN** latihan satu pertemuan selesai
- **THEN** lembar latihan peserta dan berkas kunci jawaban plus rubrik menjadi
  dua berkas berbeda, sehingga lembar peserta dapat dibagikan tanpa kuncinya

#### Scenario: Latihan selaras asesmen blueprint
- **WHEN** blueprint menetapkan bentuk asesmen satu pertemuan
- **THEN** latihan yang dihasilkan memakai bentuk itu dan menguji capaian
  pertemuan tersebut

### Requirement: Lab kode dieksekusi sampai lulus
Untuk pertemuan yang blueprint-nya menuntut lab kode, sistem SHALL menghasilkan
kode awal, langkah praktikum, dan solusi akhir, dan solusi akhir MUST dijalankan
sampai berhasil sebelum pertemuan itu dinyatakan selesai.

#### Scenario: Solusi lab berhasil dijalankan
- **WHEN** solusi lab dieksekusi
- **THEN** eksekusinya selesai tanpa galat, dan keluaran yang diharapkan dicatat
  di langkah praktikum

#### Scenario: Solusi lab gagal dijalankan
- **WHEN** eksekusi solusi lab gagal
- **THEN** sistem memperbaiki kodenya dan mengeksekusi ulang, dan jika tetap
  gagal setelah batas percobaan, tahap itu MUST dilaporkan gagal alih-alih
  menyerahkan lab yang tidak jalan

#### Scenario: Kode awal sengaja belum lengkap
- **WHEN** kode awal diserahkan ke peserta
- **THEN** bagian yang harus dikerjakan peserta ditandai eksplisit, dan kode
  awal itu tetap dapat dijalankan tanpa galat sintaks

### Requirement: Produksi paralel antarpertemuan
Sistem SHALL memproduksi pertemuan-pertemuan setelah pilot secara paralel, dan
kegagalan satu pertemuan MUST tidak menggagalkan pertemuan lain.

#### Scenario: Satu pertemuan gagal
- **WHEN** produksi satu pertemuan gagal sementara yang lain berhasil
- **THEN** sistem menyelesaikan yang lain, melaporkan pertemuan mana yang gagal
  beserta alasannya, dan menawarkan mengulang hanya pertemuan itu

### Requirement: Bahasa Indonesia dengan glosarium Inggris
Seluruh materi SHALL ditulis dalam Bahasa Indonesia, dan tiap istilah teknis
MUST diberi padanan atau penjelasan Inggris di glosarium pada kemunculan
pertamanya.

#### Scenario: Istilah teknis pertama kali muncul
- **WHEN** sebuah istilah teknis dipakai pertama kali di satu pertemuan
- **THEN** istilah itu diberi padanan Inggris di tempat dan tercatat di
  glosarium proyek
