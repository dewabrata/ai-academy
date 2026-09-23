# Spec Delta

## ADDED Requirements

### Requirement: Paket dibangun dari point final
Sistem SHALL membangun paket pertemuan hanya setelah semua point dalam pertemuan
itu berstatus siap atau eskalasi. Peran Slide dan Tugas MUST membaca point
final sebagai satu-satunya sumber isi.

#### Scenario: Semua point selesai
- **WHEN** point terakhir pertemuan 2 berstatus siap
- **THEN** Slide dan Tugas untuk pertemuan 2 dijalankan paralel dengan rujukan ke seluruh `point/*.md`

### Requirement: Handbook adalah gabungan point
Sistem SHALL membentuk `HANDBOOK.md` dengan menggabungkan judul pertemuan, daftar
isi, dan seluruh point secara berurutan tanpa mengubah isinya. Handbook juga
MUST diekspor ke DOCX.

#### Scenario: Handbook dari tiga point
- **WHEN** pertemuan memiliki point 1–3 yang sudah final
- **THEN** `HANDBOOK.md` memuat ketiga point berurutan dengan isi yang identik dengan berkas point-nya, dan `HANDBOOK.docx` terbentuk

### Requirement: Tugas sesuai jenis di blueprint
Sistem SHALL meminta peran Tugas menulis `LATIHAN.md`, `KUNCI.md`, dan
`QUIZ_AIKEN.txt` di setiap pertemuan. Selain itu, peran Tugas menulis
`PRAKTIK.md` bila jenis tugas memuat `praktik`, dan folder `lab/` dengan solusi
yang dijalankan bila jenis tugas memuat `lab-kode`.

#### Scenario: Pertemuan praktik tool
- **WHEN** blueprint menandai pertemuan dengan `Jenis: praktik`
- **THEN** paket memuat `PRAKTIK.md` dan tidak memuat folder `lab/`

#### Scenario: Pertemuan lab kode
- **WHEN** blueprint menandai pertemuan dengan `Jenis: lab-kode`
- **THEN** paket memuat `lab/awal/`, `lab/solusi/`, dan `lab/README.md`, dan solusinya dijalankan

### Requirement: Quiz AIKEN valid untuk Moodle
Sistem SHALL memeriksa bahwa `QUIZ_AIKEN.txt` memuat tepat 10 soal. Setiap soal
MUST memiliki minimal dua pilihan berlabel huruf dan satu baris
`ANSWER: <huruf>` yang menunjuk pilihan yang ada.

#### Scenario: Jawaban menunjuk pilihan yang tidak ada
- **WHEN** sebuah soal hanya punya pilihan A–C tetapi barisnya `ANSWER: D`
- **THEN** pemeriksaan quiz gagal dan menyebut nomor soalnya

### Requirement: Telaah paket setelah pemeriksa
Sistem SHALL menjalankan pemeriksa otomatis sebelum telaah paket. Reviewer
kemudian menelaah konsistensi slide, tugas, dan quiz terhadap point, dan
MUST dapat membaca `docs/PEMERIKSAAN.md`. Paket yang "Perlu revisi" diperbaiki
satu kali oleh pemilik berkasnya sebelum gate.

#### Scenario: Slide bertentangan dengan point
- **WHEN** telaah paket menemukan slide yang bertentangan dengan isi point
- **THEN** peran Slide merevisi `SLIDE.md` satu kali, lalu paket dibawa ke gate pertemuan

### Requirement: Gate pertemuan
Sistem SHALL berhenti di gate `PERTEMUAN-N` setelah paket selesai. Gate MUST
menampilkan:
- skor pemeriksa;
- point yang dieskalasi;
- semua pertanyaan "Perlu dicek-ditanyakan" dari Reviewer selama pertemuan itu;
- status telaah paket.

Jawaban teks MUST disimpan sebagai masukan pertemuan. Point direvisi mengikuti
masukan itu, lalu paket dibangun ulang.

#### Scenario: Pemilik menyetujui pertemuan
- **WHEN** gate PERTEMUAN-1 dijawab `y`
- **THEN** pertemuan 1 ditandai selesai dan produksi pertemuan 2 dimulai

#### Scenario: Pemilik memberi masukan
- **WHEN** gate PERTEMUAN-1 dijawab dengan teks
- **THEN** teks disimpan ke `materi/pertemuan-01/MASUKAN.md`, Writer merevisi point yang terkena, paket dibangun ulang, dan gate ditanyakan lagi
