# Tasks

## 1. Fondasi

- [x] 1.1 `roles.py`: tambah peran FAKTA dan TUGAS (LAB diganti), beri Writer dan Fact-Checker WebSearch/WebFetch; `run_stage` mengisi `tools=` dengan daftar tool peran (D7); verifikasi opsi CLI yang dihasilkan memuat `--tools` dengan daftar yang benar
- [x] 1.2 `academy.py`: urai `### Point` dan `### Tugas` dari blueprint (D1); verifikasi dengan blueprint buatan (point dengan capaian, tanpa capaian, jenis tugas kosong) — parser dipindah ke `rencana.py` supaya academy dan pemeriksa membaca blueprint dengan cara yang sama; 51 uji deterministik lulus
- [x] 1.3 `--klien <berkas>` menyalin konteks klien ke `docs/KLIEN.md`, dan semua peran diminta membacanya kalau ada

## 2. Loop point

- [x] 2.1 Loop Writer → Reviewer + Fact-Checker per point, status dari baris `Status:` (D2), maks. `POINT_MAKS_PUTARAN`, eskalasi (D4); verifikasi pengurai status dengan berkas buatan
- [x] 2.2 Resume: lewati point siap/eskalasi, lanjutkan putaran dari berkas telaah terakhir
- [x] 2.3 Pilot di point pertama pertemuan pilot, dengan koreksi ke `ACUAN_GAYA.md` dan revisi point pilot

## 3. Paket pertemuan

- [x] 3.1 Slide + Tugas paralel dari point final; handbook digabung Python (D5); ekspor HANDBOOK/LATIHAN/KUNCI/PRAKTIK ke DOCX dan SLIDE ke PPTX
- [x] 3.2 Pemeriksa diperbarui: kelengkapan paket per jenis tugas, status point, quiz AIKEN, sisa `[CEK-FAKTA`; verifikasi dengan data buatan
- [x] 3.3 Telaah paket setelah pemeriksa (D6), satu revisi oleh pemilik berkas
- [x] 3.4 Gate pertemuan dengan skor, eskalasi, pertanyaan terkumpul; masukan teks → revisi point → bangun ulang paket

## 4. Prompt

- [x] 4.1 `_standar.md`: aturan gaya global pemilik proyek
- [x] 4.2 `blueprint.md`: format `### Point` / `### Tugas`, salin point dari silabus apa adanya
- [x] 4.3 `writer.md`: menulis satu point sedalam handbook, penanda `[CEK-FAKTA]`, revisi dari catatan, asumsi eksplisit
- [x] 4.4 `reviewer.md`: format dan 7 lensa pemilik proyek, skor tersembunyi, mode point dan mode paket
- [x] 4.5 `fakta.md` baru; `tugas.md` menggantikan `lab.md` (latihan, kunci, praktik, lab kode, AIKEN); `slide.md` dari point + catatan trainer

## 5. Operasi

- [x] 5.1 Tahap baru `produksi`/`akhir` di `academy.py`, `control.py`, `dashboard.py`; STATE lama dipetakan ke `produksi`
- [x] 5.2 `uji/uji_asap.py` menjawab gate baru; silabus uji 2 pertemuan × 2 point (satu praktik, satu lab kode); `uji/telaah_ulang.py` dihapus (khusus format Reviewer lama)
- [x] 5.3 Uji asap Sonnet dengan `POINT_HALAMAN=1–2`; verifikasi point berurutan, loop berhenti di status, paket lengkap, quiz valid, tidak ada Bash oleh Reviewer — proyek `uji-point`: 4/4 point siap (putaran 3, 2, 3, 2), pemeriksa 100%, skor Reviewer rata-rata 4/4/4/4, 0 penolakan, 0 Bash oleh Reviewer, $16.56, 51.6 menit. Dua bug ditemukan dan diperbaiki selama uji: arah isi bernomor terbaca sebagai point (parser berhenti di blok bernomor pertama), dan Reviewer meminta penanda [CEK-FAKTA] yang sudah diverifikasi dipasang ulang (Reviewer diberi hasil Fact-Checker; Fact-Checker menang bila bertentangan)
- [x] 5.4 README dan MANUAL diperbarui; `.env.example` disesuaikan (MODEL_FAKTA/MODEL_TUGAS, BUDGET_POINT_*, POINT_HALAMAN, POINT_MAKS_PUTARAN)
