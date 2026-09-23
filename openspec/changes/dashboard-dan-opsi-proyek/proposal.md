# Proposal

## Why

Dashboard sekarang adalah panel pemantauan, bukan alat kerja. Untuk memulai
proyek, pemilik proyek harus mengunggah silabus lebih dulu lewat kartu terpisah,
lalu menekan "Mulai" di kartu lain, tanpa tempat mengisi konteks klien, pilot,
panjang point, maupun model. Tidak ada login sama sekali, padahal panel ini
menjalankan pipeline yang punya akses Bash. Kemajuan produksi tidak terlihat:
alur per point berjalan berjam-jam, tetapi yang tampil hanya nama tahap. Isi
materi hanya bisa diunduh, tidak dibaca. Semua setelan — termasuk Telegram, yang
belum pernah dinyalakan — hanya bisa diubah dengan menyunting `.env` secara
manual.

Pemilik proyek juga ingin menentukan luaran per proyek: ada pelatihan yang tidak
memerlukan slide, dan ada yang tidak memerlukan berkas biner sama sekali. Saat
ini semuanya selalu dibuat.

Terakhir, pipeline berhenti bertanya saat plafon biaya terlampaui. Untuk
produksi yang dikejar mutunya, pemilik proyek ingin menjalankannya tanpa plafon
dan membiarkan pipeline menunggu kuota lalu melanjutkan sendiri.

## What Changes

- **Login.** Dashboard meminta nama pengguna dan kata sandi dari `.env`, lalu
  menyimpan sesi di cookie. Tanpa kata sandi yang terisi, dashboard hanya
  melayani `127.0.0.1` seperti sekarang.
- **Layar buat proyek satu halaman**: seret-lepas silabus (atau tempel teks),
  unggah konteks klien, nama proyek yang diusulkan dari judul silabus, pertemuan
  pilot, panjang point, maksimum putaran, model, dan pilihan luaran.
- **Opsi per proyek** disimpan sebagai `docs/OPSI.json`, dengan bawaan dari
  `.env`:
  - ekspor DOCX dan PPTX dapat dimatikan (isi Markdown tetap dibuat);
  - slide dapat dimatikan sama sekali, sehingga peran Slide tidak dijalankan.
- **Mode tanpa plafon.** `BUDGET_* = 0` berarti tanpa batas, bukan nol dolar.
  Layar buat proyek menyediakan preset "mutu maksimal": tanpa plafon, menunggu
  kuota otomatis, dan putaran telaah lebih banyak.
- **Kemajuan produksi terlihat**: pertemuan dan point yang sedang dikerjakan,
  putaran ke berapa, status tiap point (siap / proses / eskalasi), dan berapa
  yang tersisa.
- **Gate ditampilkan menonjol**: pertanyaan utuh, tombol setuju dan berhenti,
  kolom masukan, serta tautan berkas yang perlu diperiksa.
- **Materi bisa dibaca di dashboard**: point, handbook, catatan Reviewer dan
  Fact-Checker, tanpa mengunduh.
- **Halaman pengaturan**: menyunting nilai `.env` yang aman diubah lewat UI
  (Telegram, model, plafon, setelan point, dashboard), dengan rahasia yang
  tidak pernah dikirim balik ke browser, plus tombol uji kirim pesan Telegram.
- **Tampilan baru**: terang, bersih, menyesuaikan layar HP, tanpa dependensi
  dari internet.

## Capabilities

### New Capabilities

- `opsi-proyek`: opsi luaran dan mutu per proyek, serta mode tanpa plafon.
- `dashboard-kerja`: login, layar buat proyek, kemajuan, gate, baca materi, dan
  pengaturan.

### Modified Capabilities

Tidak ada. Change sebelumnya belum diarsipkan, jadi kebutuhan baru ditulis
sebagai kapabilitas baru.

## Impact

- `dashboard.py`: ditulis ulang (tampilan, login, rute API baru).
- `opsi.py`, `setelan.py`: berkas baru.
- `academy.py`: membaca opsi proyek, melewati tahap Slide bila dimatikan,
  plafon `0` berarti tanpa batas.
- `exporter.py`: ekspor DOCX/PPTX dapat dimatikan.
- `pemeriksa.py`: pemeriksaan slide menjadi "tidak berlaku" bila slide dimatikan.
- `control.py`: menerima opsi proyek saat memulai pipeline.
- `.env.example`, README, MANUAL: setelan baru.
- Risiko: menyunting `.env` lewat UI dan mengirim pesan Telegram adalah aksi
  yang keluar dari mesin ini, jadi keduanya berada di balik login.
