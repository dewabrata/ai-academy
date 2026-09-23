# Spec Delta

## ADDED Requirements

### Requirement: Opsi luaran per proyek
Sistem SHALL menyimpan opsi produksi per proyek di `docs/OPSI.json` dan
MUST memakai nilai `.env` sebagai bawaan bila berkas itu tidak ada, sehingga
proyek lama berperilaku seperti sebelumnya.

#### Scenario: Proyek tanpa berkas opsi
- **WHEN** pipeline dijalankan pada proyek yang tidak memiliki `docs/OPSI.json`
- **THEN** opsi diambil dari `.env` dan seluruh luaran dibuat seperti bawaan

#### Scenario: Opsi ditulis dari dashboard
- **WHEN** pemilik proyek membuat proyek dengan slide dimatikan
- **THEN** `docs/OPSI.json` memuat `"slide": false` dan pipeline mengikutinya

### Requirement: Slide dapat dimatikan
Sistem SHALL melewati tahap Slide bila opsi `slide` bernilai salah. Pemeriksaan
slide MUST dilaporkan sebagai "tidak berlaku", bukan gagal, dan telaah paket
MUST NOT menuntut `SLIDE.md`.

#### Scenario: Pertemuan tanpa slide
- **WHEN** paket pertemuan dibangun dengan opsi `slide` salah
- **THEN** peran Slide tidak dijalankan, `SLIDE.md` tidak dibuat, dan pemeriksaan "slide sesuai batas" berstatus tidak berlaku

### Requirement: Ekspor biner dapat dimatikan
Sistem SHALL melewati konversi DOCX bila opsi `ekspor_docx` salah, dan konversi
PPTX bila `ekspor_pptx` salah. Sumber Markdown MUST tetap dibuat dalam kedua
kasus.

#### Scenario: Ekspor DOCX dimatikan
- **WHEN** paket dibangun dengan `ekspor_docx` salah
- **THEN** `HANDBOOK.md` tetap ada dan `HANDBOOK.docx` tidak dibuat

### Requirement: Plafon nol berarti tanpa batas
Sistem SHALL memperlakukan plafon biaya tahap yang bernilai `0` atau kosong
sebagai tanpa batas, dan MUST NOT menghentikan tahap seketika karenanya.

#### Scenario: Plafon tahap dikosongkan
- **WHEN** `BUDGET_POINT_WRITER=0` dan Writer dijalankan
- **THEN** tahap berjalan tanpa batas biaya, bukan berhenti pada nol dolar

### Requirement: Preset mutu maksimal
Sistem SHALL menyediakan preset yang menyetel seluruh plafon tahap menjadi tanpa
batas, menunggu kuota secara otomatis, dan menaikkan batas putaran telaah per
point. UI MUST menyatakan bahwa kuota langganan tetap dapat menunda pekerjaan.

#### Scenario: Preset dipilih saat membuat proyek
- **WHEN** pemilik proyek memilih preset mutu maksimal
- **THEN** opsi proyek memuat batas putaran yang dinaikkan dan pipeline dijalankan tanpa plafon tahap

### Requirement: Slide dapat dibuat menyusul
Sistem SHALL dapat membuat `SLIDE.md` untuk pertemuan yang paketnya sudah jadi
tanpa memproduksi ulang point, pada proyek yang sebelumnya dibuat dengan slide
dimatikan. Pertemuan yang sudah punya slide MUST dilewati, dan opsi proyek
diperbarui supaya produksi berikutnya ikut membuat slide.

#### Scenario: Menambahkan slide belakangan
- **WHEN** pemilik proyek meminta slide untuk pertemuan yang belum punya slide
- **THEN** peran Slide dijalankan dari point final, `SLIDE.pptx` diekspor bila ekspor PPTX aktif, dan pemeriksa dijalankan ulang

#### Scenario: Pertemuan sudah punya slide
- **WHEN** permintaan mencakup pertemuan yang sudah memiliki `SLIDE.md`
- **THEN** pertemuan itu dilewati tanpa memanggil model
