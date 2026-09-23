# Spec Delta

## ADDED Requirements

### Requirement: Login dashboard
Sistem SHALL meminta nama pengguna dan kata sandi sebelum melayani halaman
maupun rute API, bila `DASHBOARD_PASS` terisi. Sesi MUST disimpan sebagai cookie
`HttpOnly` dengan masa berlaku terbatas, dan percobaan login yang gagal berulang
MUST dibatasi.

#### Scenario: Kata sandi benar
- **WHEN** pengguna mengirim nama pengguna dan kata sandi yang cocok
- **THEN** sesi dibuat dan halaman dashboard dapat dibuka

#### Scenario: Permintaan tanpa sesi
- **WHEN** rute API dipanggil tanpa cookie sesi yang sah
- **THEN** permintaan ditolak dengan status 401

#### Scenario: Percobaan berulang gagal
- **WHEN** login gagal lima kali berturut-turut dari satu alamat
- **THEN** percobaan berikutnya dari alamat itu ditolak sementara

#### Scenario: Pemakaian lokal tanpa kata sandi
- **WHEN** `DASHBOARD_PASS` kosong dan dashboard terikat alamat lokal
- **THEN** dashboard dapat dipakai tanpa login, seperti sebelumnya

### Requirement: Membuat proyek dalam satu layar
Sistem SHALL menyediakan satu formulir yang menerima silabus (berkas yang
diseret-lepas atau teks yang ditempel), konteks klien opsional, nama proyek,
pertemuan pilot, panjang point, batas putaran, model, dan pilihan luaran, lalu
menjalankan pipeline dengan semua nilai itu.

#### Scenario: Proyek baru dari berkas silabus
- **WHEN** pemilik proyek menjatuhkan berkas silabus, mengisi nama proyek, dan menekan tombol mulai
- **THEN** silabus tersimpan di `sumber/`, opsi tersimpan di `docs/OPSI.json`, dan pipeline berjalan

#### Scenario: Nama proyek diusulkan
- **WHEN** silabus diunggah dan nama proyek masih kosong
- **THEN** UI mengusulkan nama dari judul silabus dan pemilik dapat mengubahnya

#### Scenario: Nama proyek sudah dipakai
- **WHEN** nama proyek yang diisi sudah pernah dijalankan
- **THEN** UI menolak dan meminta nama lain, tanpa menimpa proyek yang ada

### Requirement: Kemajuan produksi terlihat
Sistem SHALL menampilkan pertemuan dan point yang sedang dikerjakan, putaran ke
berapa, status tiap point, dan jumlah yang tersisa, tanpa pemilik proyek perlu
membaca log.

#### Scenario: Produksi sedang berjalan
- **WHEN** pipeline sedang mengerjakan point 3 pertemuan 2 pada putaran 2
- **THEN** dashboard menampilkan pertemuan, nomor point, putaran, serta status point lain (siap, proses, eskalasi)

### Requirement: Gate dijawab dari dashboard
Sistem SHALL menampilkan pertanyaan gate secara utuh beserta berkas yang perlu
diperiksa, dan menyediakan aksi setuju, berhenti, dan mengirim masukan teks.

#### Scenario: Gate pertemuan menunggu
- **WHEN** gate `PERTEMUAN-1` menunggu jawaban
- **THEN** dashboard menampilkan pertanyaannya utuh dan jawaban yang dikirim diteruskan ke pipeline

### Requirement: Materi dapat dibaca di dashboard
Sistem SHALL menampilkan isi berkas materi — point, handbook, catatan Reviewer
dan Fact-Checker — sebagai teks di dashboard, tanpa mengunduhnya lebih dulu.

#### Scenario: Membaca satu point
- **WHEN** pemilik proyek memilih sebuah point
- **THEN** isinya ditampilkan di dashboard

### Requirement: Pengaturan dapat diubah dari dashboard
Sistem SHALL menyediakan halaman pengaturan untuk mengubah nilai `.env` yang ada
di daftar putih, termasuk Telegram, model, plafon, dan setelan point. Nilai
rahasia MUST NOT dikirim ke browser, dan kolom yang dikosongkan MUST
mempertahankan nilai lama.

#### Scenario: Mengisi token Telegram
- **WHEN** pemilik proyek mengisi token dan chat id lalu menyimpan
- **THEN** `.env` diperbarui dengan komentar dan urutan barisnya tetap, dan token tidak pernah dikirim balik ke browser

#### Scenario: Menguji Telegram
- **WHEN** pemilik proyek menekan tombol uji Telegram
- **THEN** satu pesan uji dikirim dan hasilnya (berhasil atau pesan galat) ditampilkan

#### Scenario: Kunci di luar daftar putih
- **WHEN** permintaan menyertakan kunci `.env` yang tidak ada di daftar putih
- **THEN** kunci itu diabaikan dan tidak ditulis

### Requirement: Mengelola proyek dari dashboard
Sistem SHALL menyediakan daftar proyek dengan aksi buka, ganti nama, duplikat
setelan, dan arsipkan. Ganti nama dan arsip MUST ditolak selama pipeline proyek
itu berjalan.

#### Scenario: Mengarsipkan proyek
- **WHEN** pemilik proyek mengarsipkan sebuah proyek yang tidak sedang berjalan
- **THEN** folder proyek dipindahkan ke `workspace/.arsip/<nama>-<waktu>`, hilang dari daftar proyek, dan tidak ada berkas yang dihapus

#### Scenario: Mengarsipkan proyek yang sedang berjalan
- **WHEN** proyek yang pipeline-nya berjalan hendak diarsipkan atau diganti namanya
- **THEN** permintaan ditolak dengan alasan yang menyebut PID pipeline-nya

#### Scenario: Duplikat setelan
- **WHEN** pemilik proyek menduplikasi sebuah proyek
- **THEN** proyek baru memuat silabus, konteks klien, dan opsi yang sama, tanpa berkas materi

### Requirement: Arsip dapat dipulihkan atau dihapus permanen
Sistem SHALL menampilkan daftar arsip beserta ukuran dan waktunya, serta
menyediakan aksi pulihkan dan hapus permanen. Hapus permanen MUST menuntut nama
arsip diketik persis sebagai konfirmasi.

#### Scenario: Memulihkan arsip
- **WHEN** sebuah arsip dipulihkan dengan nama proyek yang belum dipakai
- **THEN** proyek kembali muncul di daftar dengan seluruh isinya

#### Scenario: Hapus permanen tanpa konfirmasi yang cocok
- **WHEN** konfirmasi yang diketik tidak sama dengan nama arsipnya
- **THEN** tidak ada berkas yang dihapus dan permintaan ditolak

### Requirement: Berkas dan opsi proyek dapat diubah
Sistem SHALL menyediakan pengelolaan silabus (unggah dan hapus), konteks klien
(unggah, ganti, hapus), dan opsi produksi untuk proyek yang sudah ada.

#### Scenario: Mengubah opsi proyek berjalan
- **WHEN** pemilik proyek mematikan slide pada proyek yang sudah dibuat
- **THEN** `docs/OPSI.json` diperbarui dan tahap berikutnya mengikutinya

### Requirement: Unduh materi sebagai satu berkas zip
Sistem SHALL menyediakan unduhan zip untuk seluruh materi satu proyek dan untuk
satu pertemuan. Zip bawaan MUST memuat materi ajar saja; catatan proses
(`review/`, `*.catatan.md`) hanya ikut bila diminta secara eksplisit.

#### Scenario: Mengunduh seluruh materi
- **WHEN** pemilik proyek menekan unduh semua materi
- **THEN** satu berkas zip berisi seluruh `materi/` beserta dokumen perencanaan diunduh, tanpa catatan telaah

#### Scenario: Mengunduh satu pertemuan
- **WHEN** pemilik proyek mengunduh zip satu pertemuan
- **THEN** zip hanya memuat berkas pertemuan itu

#### Scenario: Nama pertemuan tidak sah
- **WHEN** parameter pertemuan memuat path di luar folder materi
- **THEN** permintaan ditolak dan tidak ada berkas yang dikirim
