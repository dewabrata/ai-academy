# Spec Delta

## ADDED Requirements

### Requirement: Rencana disusun sebelum LMS disentuh
Sistem SHALL menyusun rencana unggah ke `docs/MOODLE.json` lebih dulu, dan
MUST NOT memanggil Moodle saat menyusunnya. Rencana MUST bisa ditinjau dan
disunting sebelum dieksekusi.

#### Scenario: Meninjau sebelum mengunggah
- **WHEN** pemilik proyek membuka tab Moodle setelah rencana tersusun
- **THEN** ia melihat nama kursus, isi tiap section, dan bobot penilaian beserta alasannya, dan belum ada apa pun yang dibuat di LMS

#### Scenario: Materi direvisi
- **WHEN** materi berubah dan rencana disusun ulang
- **THEN** rencana lama ditimpa, dan suntingan yang belum disimpan hilang dengan peringatan lebih dulu

### Requirement: Unggahan mengikuti komposisi nyata proyek
Sistem SHALL menurunkan jumlah section, berkas, quiz, dan tugas dari materi
yang benar-benar ada, bukan dari angka tetap. Pertemuan tanpa materi MUST
dilewati dan dilaporkan.

#### Scenario: Proyek tanpa slide
- **WHEN** proyek diproduksi dengan opsi slide dimatikan
- **THEN** folder materi tidak memuat SLIDE.pptx, dan itu bukan kegagalan

#### Scenario: Pertemuan belum punya materi
- **WHEN** proyek berisi enam pertemuan tetapi hanya tiga yang sudah diproduksi
- **THEN** hanya tiga yang diunggah, dan laporan menyebut tiga sisanya dilewati

### Requirement: Rencana diperiksa sebelum dieksekusi
Sistem SHALL menolak rencana yang bobotnya tidak berjumlah 100, yang nilai
lulusnya di luar 50–100, yang nomor pertemuannya tidak cocok dengan proyek,
atau yang memberi bobot pada komponen yang tidak ada.

#### Scenario: Bobot tidak berjumlah 100
- **WHEN** rencana memuat bobot berjumlah 99
- **THEN** unggahan ditolak dengan menyebut angka yang salah, dan LMS tidak disentuh

### Requirement: Tiap quiz memakai bank soalnya sendiri
Sistem SHALL membuat kategori soal privat per quiz dan menautkan soalnya satu
per satu sesuai urutan di `QUIZ_AIKEN.txt`.

#### Scenario: Kursus memakai template yang sudah punya bank soal
- **WHEN** kursus disalin dari template yang memuat bank soal
- **THEN** soal tiap hari tetap terpisah, dan quiz hari 1 tidak menarik soal hari 4

### Requirement: Hanya tool yang diizinkan boleh dipanggil
Sistem SHALL membatasi pemanggilan ke daftar putih tool, dan daftar itu
MUST NOT memuat fungsi penghapus.

#### Scenario: Kode memanggil tool di luar daftar
- **WHEN** kode memanggil `core_course_delete_courses`
- **THEN** panggilan ditolak sebelum permintaan dikirim ke Moodle
