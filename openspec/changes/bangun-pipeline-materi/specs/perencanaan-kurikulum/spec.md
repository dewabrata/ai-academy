# Spec Delta

## Purpose

Menurunkan silabus mentah menjadi rencana ajar yang bisa ditelaah manusia:
capaian pembelajaran, profil dan level peserta, peta pertemuan, lalu blueprint
rinci tiap sesi yang menjadi kontrak bagi seluruh produksi materi.

## ADDED Requirements

### Requirement: Menurunkan capaian pembelajaran
Sistem SHALL menghasilkan dokumen kurikulum yang memuat capaian pembelajaran
tingkat program dan tingkat pertemuan, dan tiap capaian MUST dinyatakan sebagai
perilaku yang teramati dan terukur.

#### Scenario: Silabus lengkap
- **WHEN** silabus memuat daftar topik per pertemuan
- **THEN** dokumen kurikulum memuat capaian program, capaian per pertemuan,
  dan peta yang menghubungkan tiap topik silabus ke capaiannya

#### Scenario: Capaian tidak terukur
- **WHEN** silabus menyebut tujuan yang tidak teramati (misalnya "memahami")
- **THEN** dokumen kurikulum menuliskannya kembali sebagai perilaku terukur dan
  mencatat penulisan ulang itu sebagai temuan

### Requirement: Menyimpulkan profil dan level peserta dari silabus
Sistem SHALL menyimpulkan profil peserta, prasyarat pengetahuan, dan level
kedalaman materi dari silabus itu sendiri, bukan dari nilai bawaan yang
dipatok di kode.

#### Scenario: Level tersirat dari silabus
- **WHEN** silabus menyiratkan peserta tanpa latar teknis
- **THEN** dokumen kurikulum menetapkan level pemula, menyebut prasyarat sebagai
  nihil, dan mewajibkan penjelasan bertahap tanpa asumsi pengetahuan awal

#### Scenario: Level tidak dapat disimpulkan
- **WHEN** silabus tidak memberi petunjuk apa pun soal peserta
- **THEN** sistem MUST melaporkan kesenjangan itu ke pengguna di gate dan
  mencatat asumsi level yang dipakainya secara eksplisit, alih-alih menebak
  diam-diam

### Requirement: Melaporkan kesenjangan silabus
Sistem SHALL melaporkan kesenjangan silabus — topik tanpa alokasi waktu, durasi
yang tidak cukup untuk capaiannya, prasyarat yang tidak diajarkan, atau topik
yang berulang — dan MUST menampilkannya ke pengguna di gate, bukan hanya
menyimpannya di dokumen.

#### Scenario: Durasi tidak memadai
- **WHEN** satu pertemuan memuat capaian yang jelas melebihi alokasi waktunya
- **THEN** sistem mencatat kesenjangan itu beserta usulan pemecahan atau
  pemangkasan, dan menampilkannya saat meminta persetujuan

#### Scenario: Prasyarat tidak diajarkan
- **WHEN** satu pertemuan menuntut pengetahuan yang tidak diajarkan pertemuan
  mana pun sebelumnya
- **THEN** sistem mencatatnya sebagai kesenjangan beserta pertemuan yang
  seharusnya menutupinya

### Requirement: Blueprint tiap pertemuan
Sistem SHALL menghasilkan blueprint tiap pertemuan yang memuat alur sesi
bertimestamp, metode pengajaran, kerangka isi, jenis asesmen, dan daftar luaran
yang harus diproduksi.

#### Scenario: Blueprint satu pertemuan
- **WHEN** dokumen kurikulum sudah disetujui
- **THEN** blueprint memuat, untuk tiap pertemuan, rincian alokasi waktu per
  segmen yang totalnya sama dengan durasi sesi, metode tiap segmen, kerangka
  isi, bentuk asesmen, dan daftar luaran

#### Scenario: Blueprint menjadi kontrak produksi
- **WHEN** produksi materi berjalan
- **THEN** setiap luaran materi MUST dapat dilacak ke satu butir blueprint, dan
  luaran yang tidak ada di blueprint tidak diproduksi

### Requirement: Glosarium istilah bersama
Sistem SHALL memelihara satu glosarium proyek berisi istilah teknis beserta
padanan Inggrisnya, dan seluruh materi MUST memakai istilah dari glosarium itu
secara konsisten.

#### Scenario: Istilah baru muncul saat produksi
- **WHEN** sebuah peran memakai istilah teknis yang belum ada di glosarium
- **THEN** istilah itu ditambahkan ke glosarium beserta padanan Inggris dan
  penjelasan singkatnya

#### Scenario: Istilah tidak konsisten antarpertemuan
- **WHEN** dua pertemuan memakai istilah Indonesia berbeda untuk konsep yang sama
- **THEN** telaah bahasa menandainya dan menyeragamkannya ke bentuk di glosarium
