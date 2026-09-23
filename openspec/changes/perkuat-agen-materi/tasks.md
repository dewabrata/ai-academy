# Tasks

## 1. Baseline dan alat ukur

- [x] 1.1 Buat `uji/uji_asap.py` dengan jawaban gate dipatok, model dapat dipilih, dan tanpa menunggu kuota; verifikasi override model lewat env berlaku tanpa mengubah `.env`
- [x] 1.2 Buat `pemeriksa.py` dengan 8 pemeriksaan deterministik; verifikasi dengan data buatan bahwa tiap pemeriksaan lulus/gagal sesuai harapan
- [x] 1.3 Jalankan uji asap baseline dengan prompt lama (Sonnet) dan simpan skornya; verifikasi `docs/PEMERIKSAAN.md` terbentuk untuk proyek `uji-baseline` — 95.8%, $8.70, 26.5 menit. Dua bug pemeriksa ditemukan dan diperbaiki sebelum v2: sub-butir bernomor di bawah `### Soal N` terhitung sebagai soal, dan lab tanpa `main.py` dilewati (kini semua skrip `solusi/` dijalankan; `lab/README.md` masuk luaran wajib)

## 2. Penegakan saat penulisan

- [x] 2.1 Buat `hooks_sdk.py`: tolak tulis di luar wilayah, tolak biner, tolak Bash terlarang, catat `tool_denied`; verifikasi 8 kasus izin dan 5 event penolakan dengan data buatan
- [x] 2.2 Umpan balik kepadatan `SLIDE.md` lewat PostToolUse; verifikasi slide 9 butir menghasilkan umpan balik yang menyebut pelanggarannya
- [x] 2.3 Pasang hook ke setiap tahap di `academy.py` dengan wilayah per tahap sesuai design D7; verifikasi signature dan kompilasi

## 3. Prompt peran

- [x] 3.1 Tambah Proses kerja, Contoh ✓/❌, dan Cek mandiri ke ketujuh prompt peran
- [x] 3.2 Tambah rubrik 1–4 dan aturan vonis ke `prompts/reviewer.md`; verifikasi `vonis_reviewer()` menghitung tabel rubrik
- [x] 3.3 Tambah larangan memakai tokoh/data contoh dan daftar aturan yang ditegakkan otomatis ke `prompts/_standar.md`
- [ ] 3.4 Ganti contoh ✓ sementara dengan contoh dari materi asli pemilik proyek — *menunggu contoh dikirim*

## 4. Integrasi telaah

- [x] 4.1 Jalankan pemeriksa sebelum menyusun `PERBAIKAN.md`, masukkan kegagalannya sebagai butir berkeparahan tinggi, dan tampilkan skor serta vonis di gate telaah

## 5. Perbandingan

- [x] 5.1 Jalankan uji asap versi baru dengan silabus dan model yang sama; verifikasi skor tercatat — 100%, $8.52, 25.9 menit, 1 penolakan (WRITER-02 menulis skrip verifikasi di akar ruang kerja). Bug pemeriksa ketiga diperbaiki: nomor soal tebal `**N.**` tidak dikenali; kedua proyek diskor ulang dengan pemeriksa yang sama
- [x] 5.2 Bandingkan dengan `python pemeriksa.py --bandingkan workspace/uji-baseline workspace/uji-v2`, sertakan biaya, jumlah penolakan, dan vonis Reviewer; laporkan juga keterbatasan satu run per versi — materi baseline ditelaah ulang dengan Reviewer baru (`uji/telaah_ulang.py`, proyek `uji-baseline-rv2`) supaya jurinya sama. Hasil: baseline LULUS/LULUS/TOLAK (2 tinggi, 3 sedang, 2 rendah); v2 TOLAK/PERLU-REVISI/TOLAK (2 tinggi, 2 sedang, 1 rendah). Mutu materi tidak terbukti naik; perbaikan v2 ada di proses (lab lebih hemat, tidak kehabisan anggaran). Pola gagal yang sama di kedua versi: ketidakcocokan antarberkas satu pertemuan (SLIDE/MODUL/KUNCI/lab) karena Writer, Slide, dan Lab berjalan paralel
