# Proposal

## Why

Silabus pelatihan sudah ada, tetapi menurunkannya menjadi materi ajar yang siap
dipakai — modul bacaan, deck presentasi, latihan berkunci, dan lab kode yang
benar-benar jalan — masih dikerjakan manual per pertemuan. Untuk silabus 16–24
sesi, pekerjaan itu berbulan-bulan, dan hasilnya tidak konsisten: kedalaman
tiap pertemuan berbeda, istilah tidak seragam, dan kunci jawaban lab sering
salah karena tidak pernah dieksekusi.

`ai-office` sudah membuktikan pola yang tepat untuk masalah sejenis: pipeline
bertahap dengan peran AI terspesialisasi dan gate persetujuan manusia di tiap
dokumen perencanaan. Yang belum ada adalah padanannya untuk produksi materi
ajar. Proyek ini membangunnya.

## What Changes

- Pipeline baru `academy.py`: silabus (Markdown/teks/Word/PDF) → materi ajar
  lengkap per pertemuan, dengan gate persetujuan manusia di tiap tahap
  perencanaan.
- Tujuh peran AI terspesialisasi menggantikan peran rekayasa perangkat lunak
  di `ai-office`: Kurikulum, Blueprint, Writer, Slide, Lab Engineer, Reviewer,
  Editor. Semua berjalan di model opus.
- **Gate pilot**: satu pertemuan contoh diproduksi penuh dan disetujui manusia
  sebelum sisa pertemuan digenerate. Ini mencegah 20 pertemuan salah gaya.
- Pembaca silabus multi-format: `.md`/`.txt` langsung, `.docx` lewat
  `python-docx`, `.pdf` lewat `pdfplumber`, dinormalkan ke satu teks.
- Empat jenis luaran per pertemuan: modul bacaan (Markdown + DOCX), deck
  presentasi (PPTX), latihan + kunci jawaban + rubrik, dan lab/project kode
  yang dieksekusi Lab Engineer sampai lulus.
- Materi berbahasa Indonesia dengan glosarium istilah Inggris yang dijaga
  konsisten lintas pertemuan oleh satu berkas glosarium bersama.
- Level dan profil peserta tidak dipatok di kode; peran Kurikulum
  menyimpulkannya dari silabus tiap proyek dan menuliskannya sebagai dokumen
  yang di-gate.
- Infrastruktur operasional diadopsi dari `ai-office`: `monitor.py` (event log
  + notifikasi/jawab gate lewat Telegram), `dashboard.py` (panel kendali web
  lokal), `control.py` (kunci satu-pipeline + pemicu dari dashboard/Telegram).

## Capabilities

### New Capabilities
- `silabus-intake`: membaca silabus dari berkas Markdown/teks/Word/PDF atau
  masukan langsung, menormalkannya, dan menyiapkan ruang kerja proyek.
- `perencanaan-kurikulum`: menurunkan capaian pembelajaran, profil & level
  peserta, dan peta pertemuan dari silabus, lalu blueprint tiap sesi.
- `produksi-materi`: memproduksi modul bacaan, deck presentasi, latihan
  berkunci, dan lab kode untuk tiap pertemuan, termasuk tahap pilot satu
  pertemuan.
- `penjaminan-mutu-materi`: menelaah akurasi teknis, kesesuaian dengan capaian
  pembelajaran, keterbacaan, dan konsistensi bahasa/istilah, lalu merangkum
  perbaikan wajib.
- `gate-persetujuan`: meminta keputusan manusia di tiap tahap kunci lewat
  terminal, dashboard, atau Telegram — setuju, revisi dengan masukan, atau
  hentikan.
- `operasi-pipeline`: orkestrasi tahap, ketahanan terhadap kegagalan dan batas
  kuota, pencatatan event, panel kendali, dan penguncian satu-pipeline.

### Modified Capabilities
<!-- Tidak ada: proyek ini belum punya spec. -->

## Impact

- Proyek baru di `D:\AI_Framework_Claude\ai-academy`, terpisah dari `ai-office`;
  tidak ada berkas `ai-office` yang diubah.
- Dependensi baru: `claude-agent-sdk`, `python-dotenv`, `python-docx`,
  `pdfplumber`, `python-pptx`.
- Prasyarat: Claude Code CLI dan langganan Claude (atau `ANTHROPIC_API_KEY`).
- Lab Engineer memerlukan tool `Bash` untuk mengeksekusi kode lab; dibatasi
  daftar perintah terlarang seperti di `ai-office`.
- Seluruh materi berbahasa Indonesia; luaran biner (DOCX/PPTX) dihasilkan lewat
  skrip Python, bukan ditulis langsung oleh agent.
