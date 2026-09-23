# Design

## Context

Keputusan pemilik proyek (22 Sep 2026): login pengguna + kata sandi; layar buat
proyek memuat unggah silabus (seret-lepas), unggah konteks klien, nama proyek
dan pilot, panjang point, putaran, model, serta pilihan ekspor DOCX/PPTX dan
slide dibuat atau tidak; opsi disimpan per proyek dengan bawaan dari `.env`;
tampilan terang dan bersih untuk laptop dan HP; pengaturan (termasuk Telegram)
bisa diubah dari dashboard; produksi dapat dijalankan tanpa plafon sampai
materinya bagus.

Batasan yang mengikat:

- Dashboard adalah satu berkas Python dengan `http.server`, tanpa build step.
  Menambah framework berarti menambah rantai pasok dan kebutuhan internet.
- Panel ini menjalankan pipeline, dan peran Tugas di dalamnya punya `Bash`.
  Karena itu setiap penambahan permukaan (menyunting `.env`, mengirim pesan
  Telegram) harus berada di balik login.

## Goals / Non-Goals

**Goals:**

- Satu layar untuk memulai proyek, dari silabus sampai opsi.
- Kemajuan alur per point terlihat tanpa membaca log.
- Setelan yang sering diubah tidak menuntut menyunting `.env` manual.

**Non-Goals:**

- Banyak akun pengguna dan peran akses. Satu akun, sesuai keputusan pemilik.
- Menyunting materi dari dashboard. Dashboard membaca; yang menulis adalah peran
  dan pemilik proyek lewat editor.
- Mengubah alur produksi itu sendiri.

## Decisions

### D1. Login memakai kredensial `.env` dan cookie sesi

`DASHBOARD_USER` dan `DASHBOARD_PASS` sudah ada. Login membandingkan keduanya
dengan `hmac.compare_digest`, lalu memberi cookie `sesi` berisi token acak 32
byte yang disimpan di memori proses. Cookie `HttpOnly`, `SameSite=Strict`, umur
`DASHBOARD_SESI_JAM` (bawaan 12 jam). Token hilang saat dashboard di-restart —
itu diterima, karena memaksa login ulang setelah setiap restart lebih aman
daripada menyimpan token ke disk.

Kalau `DASHBOARD_PASS` kosong **dan** host lokal, dashboard tetap jalan tanpa
login seperti sekarang, supaya pemakaian di laptop sendiri tidak berubah. Kalau
host bukan lokal, kata sandi tetap wajib.

Percobaan login dibatasi: setelah 5 kali gagal dari satu alamat, ditolak selama
5 menit. Tanpa itu, satu kata sandi di jaringan lokal terlalu mudah ditebak.

### D2. Opsi proyek di `docs/OPSI.json`, bawaan dari `.env`

Pipeline harus bisa dijalankan dari terminal tanpa dashboard, jadi opsi tidak
boleh hanya hidup di UI. `opsi.py` membaca `docs/OPSI.json` kalau ada, dan
jatuh ke nilai `.env` kalau tidak. Proyek lama tanpa berkas itu berjalan persis
seperti sekarang.

Isinya:

```json
{"slide": true, "ekspor_docx": true, "ekspor_pptx": true,
 "point_halaman": "10–20", "point_maks_putaran": 3, "model": "opus"}
```

`model` dan setelan point ditulis ke `OPSI.json` juga, bukan ke `.env`, supaya
dua proyek dengan kebutuhan berbeda tidak saling menimpa.

### D3. `BUDGET_* = 0` berarti tanpa plafon

Nilai `0` sebelumnya diteruskan apa adanya ke `max_budget_usd`, yang berarti
tahap berhenti seketika. Itu jebakan: pemilik proyek yang ingin "tanpa batas"
justru mendapat pipeline yang tidak menghasilkan apa pun. Sekarang `0` atau
kosong diterjemahkan menjadi `None` (tanpa batas), sama seperti perilaku
`BUDGET_PROYEK` yang sudah begitu.

Preset "mutu maksimal" di layar buat proyek menyetel: semua plafon tahap tanpa
batas, `QUOTA_WAIT=auto` dengan `QUOTA_WAIT_MAX_HOURS` besar (menunggu reset
mingguan), dan `point_maks_putaran` 5. Yang tidak bisa dijanjikan adalah kuota
langganan itu sendiri — pipeline hanya bisa menunggu resetnya, dan itu
dinyatakan apa adanya di UI.

### D4. Slide dimatikan = tahap tidak dijalankan

Perbedaan yang disengaja dengan ekspor: mematikan ekspor hanya melewati
konversi biner (murah, isi tetap ada), sedangkan mematikan slide membuat peran
Slide tidak dipanggil sama sekali (hemat biaya model). Pemeriksa menandai
pemeriksaan slide sebagai "tidak berlaku", bukan gagal, supaya skor tidak jatuh
karena pilihan yang disengaja.

### D5. Rahasia tidak pernah dikirim ke browser

Halaman pengaturan menampilkan kunci rahasia (token Telegram, API key, kata
sandi dashboard) sebagai status `terisi`/`kosong`, bukan nilainya. Nilai baru
hanya ditulis kalau pengguna mengetik sesuatu; kolom kosong berarti "biarkan apa
adanya". Penulisan `.env` mempertahankan komentar dan urutan baris, dan hanya
kunci yang ada di daftar putih yang boleh diubah.

### D6. Satu halaman, tanpa dependensi luar

Tampilan tetap ditulis tangan: CSS variabel warna, tata letak `grid` yang
berubah menjadi satu kolom di bawah 900 px, dan JavaScript tanpa framework.
Alasannya sama seperti sebelumnya — dashboard harus bisa dibuka di mesin tanpa
internet, dan berkas tunggal memudahkan meninjau apa yang dijalankan browser.

### D7. Membaca materi lewat rute yang sudah ada

`/api/berkas` sudah melayani berkas di dalam ruang kerja proyek dengan
pemeriksaan path. Pembacaan di dashboard memakai rute yang sama dengan parameter
`mentah=1` untuk ditampilkan sebagai teks, jadi tidak ada permukaan baru yang
perlu diamankan.

## Risks / Trade-offs

- **Menyunting `.env` dari UI** dapat mematikan pengaman (mis. mengosongkan
  kata sandi). Mitigasi: daftar putih kunci, login wajib, dan peringatan di UI
  ketika kata sandi dikosongkan sementara host bukan lokal.
- **Tanpa plafon** berarti tidak ada rem otomatis. Mitigasi: biaya berjalan
  ditampilkan besar di kartu kemajuan, dan preset ini harus dipilih sadar, bukan
  bawaan.
- **Token sesi di memori** hilang saat restart. Diterima; login ulang murah.
- **Uji kirim Telegram** mengirim pesan nyata ke chat. Itu memang tujuannya, dan
  hanya bisa dipicu setelah login.

## Migration Plan

Proyek lama tanpa `docs/OPSI.json` memakai bawaan `.env` dan berperilaku sama
seperti sebelumnya. Tidak ada konversi data. Dashboard lama tidak perlu
dijalankan lagi.
