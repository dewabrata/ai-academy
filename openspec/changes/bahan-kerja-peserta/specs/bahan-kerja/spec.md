# Spec Delta

## ADDED Requirements

### Requirement: Berkas kerja peserta diserahkan
Sistem SHALL menghasilkan folder `bahan/` per pertemuan berisi `awal/`,
`jadi/`, dan `README.md`, untuk jenis tugas apa pun. `bahan/awal/` MUST memuat
keadaan awal yang dibuka peserta, dan `bahan/jadi/` MUST memuat keadaan benar
sesudah pekerjaan pertemuan itu selesai.

#### Scenario: Materi menceritakan sebuah aplikasi
- **WHEN** handbook menampilkan isi `reminder-routes.js` dan menyuruh peserta mengubahnya
- **THEN** berkas itu ada di `bahan/awal/` dengan bagian yang dikerjakan ditandai, dan versi benarnya ada di `bahan/jadi/`

#### Scenario: Materi spreadsheet
- **WHEN** pertemuan melatih merapikan berkas rekap
- **THEN** `bahan/awal/` memuat rekap mentah dan `bahan/jadi/` memuat hasil rapinya

#### Scenario: Pertemuan tanpa berkas kerja
- **WHEN** blueprint menulis `Bahan: tidak` untuk sebuah pertemuan
- **THEN** `bahan/` tidak dibuat dan pemeriksaannya tidak berlaku

### Requirement: Blueprint menetapkan isi bahan
Sistem SHALL meminta blueprint menulis baris `Bahan:` di bagian `### Tugas`
tiap pertemuan, berisi satu kalimat tentang berkas kerja yang harus diserahkan,
atau `tidak`.

#### Scenario: Bahan berlanjut antarpertemuan
- **WHEN** pertemuan 2 melanjutkan aplikasi dari pertemuan 1
- **THEN** blueprint menyebutnya, dan `bahan/awal/` pertemuan 2 sama dengan `bahan/jadi/` pertemuan 1

### Requirement: Berkas spreadsheet dari sumber teks
Sistem SHALL meminta peran menulis berkas spreadsheet sebagai `.csv`, dan
`exporter.py` SHALL menghasilkan `.xlsx` darinya. Peran MUST NOT menulis berkas
biner secara langsung.

#### Scenario: Rekap contoh
- **WHEN** peran Tugas menulis `bahan/awal/rekap-mentah.csv`
- **THEN** ekspor menghasilkan `bahan/awal/rekap-mentah.xlsx` dengan isi yang sama

#### Scenario: Ekspor XLSX dimatikan
- **WHEN** opsi proyek `ekspor_xlsx` bernilai salah
- **THEN** hanya `.csv` yang diserahkan, dan pemeriksaan `.xlsx` tidak berlaku

### Requirement: Berkas yang ditampilkan isinya harus ada
Sistem SHALL memeriksa bahwa setiap berkas yang **ditampilkan isinya** di point
— nama berkas diikuti blok kode — benar-benar ada di `bahan/` atau `lab/`
pertemuan itu.

#### Scenario: Materi menampilkan berkas yang tidak diserahkan
- **WHEN** point menampilkan isi `tests/reminder.test.js` tetapi berkas itu tidak ada di `bahan/` maupun `lab/`
- **THEN** `docs/PEMERIKSAAN.md` menandainya gagal beserta nama berkasnya
