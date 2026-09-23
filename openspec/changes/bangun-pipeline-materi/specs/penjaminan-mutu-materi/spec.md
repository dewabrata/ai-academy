# Spec Delta

## Purpose

Menelaah materi yang sudah diproduksi terhadap akurasi teknis, kesesuaian
dengan capaian pembelajaran, keterbacaan bagi level peserta, dan konsistensi
bahasa, lalu merangkumnya menjadi daftar perbaikan wajib yang terurut.

## ADDED Requirements

### Requirement: Telaah akurasi teknis dan kesesuaian capaian
Sistem SHALL menelaah tiap pertemuan terhadap kebenaran teknis isi dan
kesesuaiannya dengan capaian pembelajaran, dan MUST menyebut berkas serta
bagian tepatnya untuk tiap temuan.

#### Scenario: Pernyataan teknis salah
- **WHEN** modul memuat pernyataan teknis yang salah atau usang
- **THEN** telaah mencatatnya beserta berkas, bagian, koreksi yang benar, dan
  tingkat keparahannya

#### Scenario: Capaian tidak tertutup
- **WHEN** satu capaian pembelajaran tidak tertutup materi pertemuannya
- **THEN** telaah mencatatnya sebagai temuan keparahan tinggi beserta materi
  yang perlu ditambahkan

#### Scenario: Materi di luar silabus
- **WHEN** materi memuat isi yang tidak dapat dilacak ke capaian mana pun
- **THEN** telaah mencatatnya beserta usulan menghapus atau memindahkannya

### Requirement: Telaah keterbacaan terhadap level peserta
Sistem SHALL menelaah keterbacaan materi terhadap level peserta yang ditetapkan
dokumen kurikulum.

#### Scenario: Materi terlalu sulit bagi levelnya
- **WHEN** materi memakai konsep di luar prasyarat level peserta tanpa
  menjelaskannya
- **THEN** telaah mencatatnya beserta penjelasan atau analogi yang perlu
  ditambahkan

#### Scenario: Beban satu segmen berlebihan
- **WHEN** satu segmen memuat konsep baru jauh lebih banyak daripada segmen lain
- **THEN** telaah mencatat ketidakseimbangan itu beserta usulan pemecahan

### Requirement: Telaah bahasa dan konsistensi istilah
Sistem SHALL menelaah bahasa, ejaan, dan konsistensi istilah lintas pertemuan
terhadap glosarium proyek.

#### Scenario: Istilah menyimpang dari glosarium
- **WHEN** satu pertemuan memakai istilah yang berbeda dari glosarium untuk
  konsep yang sama
- **THEN** telaah menyeragamkannya ke bentuk di glosarium

#### Scenario: Padanan Inggris belum ada
- **WHEN** sebuah istilah teknis dipakai tanpa padanan Inggris di glosarium
- **THEN** telaah menambahkannya ke glosarium

### Requirement: Daftar perbaikan wajib terurut keparahan
Sistem SHALL merangkum seluruh temuan telaah menjadi satu daftar perbaikan
wajib, terurut dari keparahan tertinggi, dan tiap butir MUST menyebut berkas
sasaran serta langkah perbaikannya.

#### Scenario: Ada temuan
- **WHEN** telaah menghasilkan temuan
- **THEN** daftar perbaikan memuat tiap temuan dengan berkas sasaran, langkah
  perbaikan, dan keparahan, terurut dari yang tertinggi

#### Scenario: Tidak ada temuan
- **WHEN** telaah tidak menemukan masalah
- **THEN** daftar perbaikan dinyatakan kosong secara eksplisit dan pipeline
  melanjut ke penyelesaian tanpa putaran revisi

### Requirement: Putaran revisi berulang sampai pengguna berhenti
Sistem SHALL menawarkan putaran revisi setelah tiap telaah, dan MUST menelaah
ulang materi setelah revisi dikerjakan.

#### Scenario: Pengguna memilih memperbaiki
- **WHEN** pengguna memilih mengerjakan daftar perbaikan
- **THEN** sistem merevisi materi sesuai daftar itu, menelaah ulang, dan
  menawarkan putaran berikutnya

#### Scenario: Pengguna memilih berhenti
- **WHEN** pengguna memilih berhenti walau daftar perbaikan masih ada isinya
- **THEN** sistem menyelesaikan proyek dan MUST mencatat temuan yang tidak
  dikerjakan di ringkasan akhir
