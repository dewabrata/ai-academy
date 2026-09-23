# Tasks

## 1. Opsi proyek

- [x] 1.1 `opsi.py`: baca/tulis `docs/OPSI.json` dengan bawaan dari `.env`; verifikasi proyek tanpa berkas opsi memakai bawaan lama
- [x] 1.2 `academy.py`: plafon `0`/kosong → tanpa batas (D3); lewati tahap Slide bila opsi `slide` salah; teruskan opsi ke ekspor
- [x] 1.3 `exporter.py`: bendera `docx`/`pptx` pada `ekspor_pertemuan`; verifikasi berkas biner tidak dibuat saat dimatikan
- [x] 1.4 `pemeriksa.py`: pemeriksaan slide "tidak berlaku" bila slide dimatikan; paket lengkap tidak menuntut `SLIDE.md`

## 2. Fondasi dashboard

- [x] 2.1 `setelan.py`: baca `.env` (rahasia hanya sebagai status terisi/kosong), tulis dengan komentar dan urutan dipertahankan, daftar putih kunci; uji baca-tulis dengan berkas buatan
- [x] 2.2 Login: cookie sesi `HttpOnly`, batas percobaan gagal, semua rute API di balik sesi; verifikasi 401 tanpa cookie dan lolos dengan cookie
- [x] 2.3 `control.py`: `start()` menerima opsi proyek dan menulis `OPSI.json` sebelum pipeline jalan

## 3. Layar

- [x] 3.1 Layar buat proyek: seret-lepas silabus atau tempel teks, konteks klien, nama usulan dari judul, pilot, panjang point, putaran, model, opsi luaran, preset mutu maksimal
- [x] 3.2 Kartu kemajuan: pertemuan/point/putaran berjalan, status tiap point, sisa pekerjaan, biaya berjalan, status kuota
- [x] 3.3 Kartu gate: pertanyaan utuh, tombol setuju/berhenti, kolom masukan, tautan berkas
- [x] 3.4 Pembaca materi: daftar berkas point/handbook/review, isinya ditampilkan sebagai teks
- [x] 3.5 Halaman pengaturan: Telegram (dengan tombol uji kirim), model, plafon, setelan point, dashboard
- [x] 3.6 Tampilan terang, bersih, satu kolom di layar sempit, tanpa dependensi internet

## 4. Verifikasi

- [x] 4.1 Uji rute dengan `curl`: login gagal/berhasil, 401 tanpa sesi, buat proyek (tanpa menjalankan model), baca berkas, simpan pengaturan
- [x] 4.2 Uji opsi: proyek dengan slide dimatikan dan ekspor dimatikan menghasilkan luaran yang benar (memakai data buatan, tanpa model)
- [x] 4.3 README, MANUAL, `.env.example` diperbarui

## 5. CRUD proyek

- [x] 5.1 `control.py`: arsipkan, daftar arsip, pulihkan, hapus permanen (dengan konfirmasi nama), ganti nama, duplikat setelan, hapus konteks klien — semuanya menolak saat pipeline berjalan
- [x] 5.2 Halaman **Proyek**: tabel proyek (tahap, pertemuan, biaya, diubah, status) dengan aksi Buka/Ganti nama/Duplikat/Arsipkan, plus tabel Arsip dengan Pulihkan dan Hapus permanen
- [x] 5.3 Tab **Berkas & opsi** per proyek: unggah/hapus silabus, unggah/hapus konteks klien, dan menyunting opsi produksi
- [x] 5.4 Verifikasi: 20 uji fungsi CRUD dengan ruang kerja sementara, dan uji rute HTTP (unggah klien, opsi, duplikat, ganti nama, arsip, hapus permanen)

## 6. Unduhan dan slide susulan

- [x] 6.1 `/api/zip`: zip materi per proyek dan per pertemuan, dengan opsi menyertakan catatan telaah; verifikasi isi zip dan penolakan path di luar folder materi
- [x] 6.2 `academy.py --slide N|semua` + tombol di dashboard: membuat slide menyusul dari point final, melewati pertemuan yang sudah punya slide, memperbarui `OPSI.json`; verifikasi jalur "sudah punya slide" tanpa memanggil model
