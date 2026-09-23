# Spec Delta

## ADDED Requirements

### Requirement: Penulisan dibatasi ke wilayah peran
Sistem SHALL menolak penulisan berkas oleh peran produksi di luar folder
pertemuan yang sedang dikerjakannya, dan MUST mengembalikan alasan penolakan
kepada peran itu supaya ia dapat memperbaikinya dalam tahap yang sama.

#### Scenario: Writer menulis ke pertemuan lain
- **WHEN** peran produksi untuk pertemuan 2 mencoba menulis ke `materi/pertemuan-03/`
- **THEN** penulisan ditolak dengan alasan yang menyebut folder yang diizinkan

#### Scenario: Peran produksi menyentuh glosarium bersama
- **WHEN** peran produksi mencoba menulis `docs/GLOSARIUM.md`
- **THEN** penulisan ditolak dan peran diarahkan menulis ke `ISTILAH.md` di folder pertemuannya

#### Scenario: Peran menulis berkas biner
- **WHEN** peran mana pun mencoba menulis berkas `.docx` atau `.pptx`
- **THEN** penulisan ditolak dan peran diingatkan bahwa biner dihasilkan dari sumber Markdown

### Requirement: Kepadatan slide ditegakkan saat ditulis
Sistem SHALL memeriksa `SLIDE.md` setiap kali peran Slide menulisnya, dan MUST
mengembalikan pelanggaran batas kepadatan kepada peran Slide dalam tahap yang
sama, bukan menunggu telaah akhir.

#### Scenario: Slide melebihi batas
- **WHEN** peran Slide menulis `SLIDE.md` dengan slide yang melebihi batas butir atau kata
- **THEN** peran Slide menerima daftar pelanggarannya segera setelah penulisan dan dapat memperbaikinya

#### Scenario: Slide sesuai batas
- **WHEN** `SLIDE.md` yang ditulis tidak melanggar batas
- **THEN** tidak ada umpan balik tambahan dan tahap berlanjut
