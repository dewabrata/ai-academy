# Katalog jebakan

Semua yang di bawah ini **benar-benar terjadi** di `ai-academy`. Bentuknya:
gejala → akar masalah → aturan. Baca bagian yang relevan sebelum menulis kode
sejenis, bukan sesudah bug-nya muncul.

---

## A. Batas, pemotongan, dan pesan yang hilang

### A1. Pesan terakhir melewati batas, lalu terpotong di tengah markup

**Gejala.** Berkas lampiran terkirim ke Telegram, pertanyaan gate-nya tidak.
Log hanya berbunyi `telegram gagal: HTTP Error 400: Bad Request`. Pipeline
menunggu jawaban atas pertanyaan yang tidak pernah terlihat.

**Akar masalah.** Jatah isi dihitung begini:

```python
jatah = BATAS - max(len(kepala), len(ekor)) - 60      # SALAH
```

Pesan **terakhir** memuat kepala *dan* ekor sekaligus, jadi ia bisa 114 karakter
melewati batas. `text[:BATAS]` lalu memotongnya tepat di tengah `<code>` pada
ekor — `<code>` terbuka 3 kali, tertutup 2 — dan Telegram menolak HTML yang
tagnya menggantung. Yang gagal justru pesan yang membawa pertanyaan dan tombol.

**Aturan.**
- Sisihkan ruang untuk **semua** bagian yang akan ada di pesan itu, bukan yang
  terpanjang di antaranya.
- Pemotongan darurat harus sadar-markup: buang tag/entitas yang terbelah di
  ujung, tutup yang masih terbuka, dan hasilnya tetap muat batas **termasuk tag
  penutup yang ia tambahkan sendiri**.
- Hitung panjang setelah escaping, bukan sebelumnya — `&` jadi `&amp;`
  memanjangkan teks.
- Sediakan jalur cadangan tanpa format kalau kiriman ber-format gagal.

### A2. Memotong dari depan membuang bagian terpenting

**Gejala.** `question[:2600]` menyisakan pembukaan dan membuang kesimpulan —
padahal bagian yang harus diputuskan manusia ada di ujung.

**Aturan.** Kalau harus memotong, pertahankan **awal dan akhir**, beri tanda di
tengah bahwa ada bagian yang dilewati, dan sebutkan di mana teks penuhnya.
Lebih baik lagi: jangan potong, bagi jadi beberapa pesan.

### A3. Batas yang tidak pernah disebutkan

**Gejala.** Kutipan silabus dibatasi 25 baris. Yang 60 baris tidak pernah
sampai, dan tidak ada yang tahu ada yang hilang.

**Aturan.** Batas apa pun yang memotong isi harus **mengumumkan dirinya**
(`(+60 baris lagi)`) dan menyebut cara melihat sisanya. Batas diam adalah
kehilangan data.

---

## B. Nilai kosong, nilai bawaan, dan keadaan basi

### B1. Kolom kosong jatuh ke nilai bawaan

**Gejala.** Menekan tombol Unggah tanpa memilih kategori tetap membuat kursus —
di tempat yang tidak diniatkan. Satu kursus nyata terbentuk di LMS produksi.

**Akar masalah.** `body.get(k) or os.getenv(ENV)` tidak membedakan "tidak
dikirim" dari "dikirim tetapi kosong".

**Aturan.** Bedakan keduanya secara eksplisit. Lihat `_id()` di
[integrasi.md](integrasi.md#3-pilih-dari-nama-bukan-ketik-id).

### B2. Berkas hasil yang basi

**Gejala.** Dashboard menampilkan "sudah diunggah ke kursus 184" padahal kursus
itu sudah dihapus berminggu-minggu lalu.

**Aturan.** Jangan percaya berkas hasil sebagai bukti keadaan sistem luar.
Verifikasi ke sumbernya, dan sediakan **tiga** keadaan: ada / tidak ada /
tidak bisa diperiksa. Dua keadaan memaksa "tidak bisa diperiksa" berbohong jadi
salah satu dari keduanya.

### B3. Lock dari proses yang sudah mati

**Gejala.** Proyek tampak sedang berjalan selamanya. Lock-nya berumur 148 jam
dan PID-nya sudah tidak ada.

**Aturan.** Keberadaan berkas lock bukan bukti. **Periksa PID-nya.** Laporkan
lock mati sebagai kedaluwarsa; jangan diklaim diam-diam oleh proses lain.

### B4. Jawaban gate yang tertinggal

**Gejala.** Gate berikutnya langsung terjawab sendiri oleh jawaban gate
sebelumnya.

**Aturan.** Hapus berkas jawaban **setelah terbaca**, dan buang jawaban
tertinggal **saat pipeline mulai**.

---

## C. Balapan dan keunikan

### C1. Periksa-lalu-buat yang balapan

**Gejala.** Satu klik dua kali menghasilkan dua kategori bernama sama, padahal
pemeriksaan nama kembar sudah ada.

**Akar masalah.** Dua permintaan berangkat berbarengan; keduanya membaca daftar
sebelum salah satunya sempat membuat apa pun, jadi keduanya melihat "belum ada".

**Aturan.** Kunci mencakup pembacaan **dan** pembuatan. Kunci di antarmuka saja
tidak cukup — dua tab atau satu muat ulang tetap menyelinap.

### C2. Keunikan berlaku lebih luas daripada dugaan

Lihat [integrasi.md](integrasi.md#4-keunikan-balapan-dan-idempotensi).

### C3. Satu antrean pesan, dua pembaca

**Gejala.** Uji Telegram dijalankan selagi pipeline berjalan. Balasan "test"
diterima pipeline sebagai jawaban gate yang sesungguhnya — satu tahap diulang,
$0.28 terbuang.

**Aturan.** `getUpdates` punya satu offset bersama. Hanya satu proses yang boleh
mendengarkan. Jangan menguji bot selagi pipeline berjalan; lingkungan staging
sebaiknya punya bot sendiri.

---

## D. Proses, kode, dan deploy

### D1. Proses yang berjalan memegang kode lama

**Gejala.** Perbaikan exporter sudah di-commit, di-pull, dan ada di disk. Tetapi
semua deck yang dihasilkan tetap format lama.

**Akar masalah.** Python memuat modul sekali saat proses start. Proses yang
sudah berjalan tidak akan melihat perubahan di disk.

**Aturan.**
- Selalu bedakan **"ada di disk"** dari **"dipakai proses yang hidup"**.
- Perbaikan di tengah run baru berlaku di run berikutnya. Katakan ini saat
  melapor.
- Kalau antarmuka melayani HTML dari konstanta modul, restart diperlukan untuk
  perubahan antarmuka. Verifikasi dengan membandingkan yang disajikan dengan
  yang ada di berkas:

  ```python
  sama = (halaman_yang_disajikan == modul_dari_disk.HALAMAN)   # sha256 keduanya
  ```

  Cap waktu systemd bisa menyesatkan; perbandingan isi tidak.

### D2. Proses baru membaca kode baru — jadi tidak semua butuh restart

Kalau control plane menjalankan pekerjaan lewat `subprocess.Popen`, pekerjaan
berikutnya otomatis memakai kode terbaru walaupun control plane-nya belum
restart. Periksa dulu apakah control plane memanggil modul itu **di prosesnya
sendiri**:

```bash
grep -c "import exporter\|exporter\." dashboard.py     # 0 = tidak perlu restart
```

Jangan menyuruh restart tanpa memeriksa ini.

### D3. `EnvironmentFile` menimpa `Environment=` apa pun urutannya

**Gejala.** `Environment=DASHBOARD_HOST=0.0.0.0` ditulis **sesudah**
`EnvironmentFile=`, tetapi nilai dari `.env` tetap menang.

**Aturan.** Di systemd, `EnvironmentFile` selalu menimpa `Environment=`.
Setelan khas mesin harus ditulis di berkas env mesin itu, bukan diakali lewat
unit.

### D4. CRLF ikut masuk ke nilai `.env`

**Gejala.** `.env` disalin dari Windows ke Linux. Token jadi 33 karakter dan
ditolak, tanpa pesan yang jelas.

**Aturan.** Normalkan ke LF saat menyalin, lalu verifikasi:
`grep -c $'\r' .env` harus 0. Bandingkan sha256 kedua berkas, bukan panjangnya.

### D5. Cache paket yang basi

**Gejala.** `npm install -g <paket>` memasang versi beberapa ratus rilis di
belakang `latest`.

**Aturan.** Setelah memasang, **bandingkan versi terpasang dengan
`npm view <paket> version`**. Kalau berbeda: `npm cache clean --force` lalu
pasang ulang dengan `@latest`.

### D6. Jangan sentuh konfigurasi bersama di server bersama

Server staging yang sudah menjalankan aplikasi lain:

- Survei dulu: port yang didengarkan, container, pemilik tiap port, firewall.
  **Jangan ubah apa pun di langkah ini.**
- Pakai **systemd user service** — `/etc/systemd/system` tidak disentuh.
- Pakai prefix npm milik pengguna (`~/.npm-global`) — `/usr/local` tidak
  disentuh, dan tidak perlu sudo.
- Menambah `server_name` ke nginx yang konfignya di-mount read-only milik
  aplikasi lain berarti membuat ulang container-nya. Itu bukan "tidak
  mengganggu". Katakan terus terang dan tawarkan jalan yang benar-benar tidak
  menyentuh apa pun.
- Setelah deploy, **buktikan aplikasi lain masih hidup** — bukan hanya bahwa
  milikmu hidup.

---

## E. Claude Agent SDK

| Jebakan | Akibat | Yang benar |
|---|---|---|
| Mengisi `allowed_tools=` saja | Peran tetap bisa memakai tool lain | Isi `tools=` |
| `max_budget_usd=0` untuk "tanpa batas" | Tahap berhenti seketika | Kirim `None` |
| Menambahkan `total_cost_usd` tiap `ResultMessage` | Biaya terhitung berlipat, plafon proyek berhenti dini | `ResultMessage` membawa **total tahap**; tambahkan selisihnya saja |
| Mengandalkan hook di `.claude/settings.json` | Tidak pernah dimuat kalau `setting_sources=[]` | Tulis hook Python milik SDK |
| Mencatat alias model (`opus`) | Tidak bisa dirunut saat alias berpindah | Catat `msg.data["model"]` dari `SystemMessage` init |
| Aturan hanya ditulis di prompt | Pelanggaran baru ketahuan di akhir | Tegakkan di `PreToolUse` |

---

## F. Dokumen dan berkas hasil

### F1. Elemen ditaruh di posisi tetap lalu menimpa isi

**Gejala.** Blok kode ditaruh di 2/3 tinggi slide. Di hampir setiap slide yang
punya butir **dan** kode, keduanya bertumpuk.

**Aturan.** Hitung tata letak dari isinya: tinggi judul menentukan di mana badan
mulai, tinggi butir menentukan di mana blok berikutnya mulai. Jangan ada
koordinat tetap untuk elemen yang ukurannya berubah-ubah.

### F2. Mematikan efek tema tidak cukup satu tempat

**Gejala.** `shape.shadow.inherit = False` sudah diset, bayangannya tetap
tercetak.

**Akar masalah.** `<p:style>` milik bentuk masih menunjuk `effectRef` tema.
Selama rujukan itu ada, efeknya tetap digambar.

**Aturan.** Matikan keduanya. Dan **verifikasi di XML**, bukan dari pratinjau —
halo tipis di render LibreOffice bisa sekadar antialias, bukan bayangan.

### F3. Pratinjau bukan bukti, tetapi wajib dilihat

- Render hasilnya jadi gambar dan **lihat**. Setelah lama menatap kode, kamu
  melihat yang kamu harapkan, bukan yang tergambar.
- Tapi jangan percaya pratinjau untuk hal yang alatnya ganti huruf: lebar huruf
  pengganti berbeda, jadi "muat" atau "meluber" di pratinjau bisa salah. Pakai
  huruf yang ikut paket Office, atau beri kelonggaran ~10%.
- Validasi berkasnya juga dengan alat, bukan hanya mata.

### F4. Nilai yang bentuknya tertukar

`fraction` pada jawaban soal Moodle adalah **pecahan** (`1`/`0`), bukan persen.
`fraction: 100` ditolak. Baca skema, jangan menebak dari namanya.

### F5. Keluaran yang dihasilkan tetapi tidak pernah diserahkan

**Gejala.** 31 berkas ditampilkan isinya di materi, tidak satu pun benar-benar
diserahkan ke peserta.

**Aturan.** Kalau isi sebuah berkas ditampilkan, berkas itu harus ada di daftar
yang diserahkan. Ini bisa diperiksa deterministik — periksa, jangan percaya.

### F6. Satu peran tidak pernah diminta bekerja

**Gejala.** Peran APLIKASI ada, prompt-nya ada, tetapi `prompt_paket()` tidak
pernah menyebut `bahan/`. Peran itu tidak pernah menghasilkan apa pun, dan tidak
ada yang menyadarinya sampai pengguna bertanya.

**Aturan.** Setiap peran yang terdaftar harus punya **uji yang membuktikan
luarannya diminta**. Peran yang tidak pernah dipanggil adalah kegagalan senyap.

---

## G. Lingkungan pengembangan

### G1. Heredoc Git Bash merusak backslash

**Gejala.** Regex `\b` dan `\1` di dalam heredoc berubah jadi karakter kendali
di berkas sumber. Kodenya tampak benar di layar, tetapi tidak jalan.

**Aturan.** Jangan menulis kode berisi backslash lewat heredoc di Git Bash.
Tulis skrip patch dengan alat tulis berkas, lalu jalankan skripnya. Setelah
menulis, pindai berkas sumber dari karakter kendali.

### G2. `pgrep -f` mencocoki dirinya sendiri

Baris perintah pembungkus memuat polanya, jadi proses tampak selalu hidup.
Pakai `pgrep -f "nama[.]py"`.

### G3. Menjalankan uji dengan runner yang salah

**Gejala.** Lab dinyatakan gagal padahal tidak — dijalankan dengan `node --test`
sementara proyeknya memakai Jest.

**Aturan.** Deteksi runner dari berkas proyeknya. Dan saat melaporkan kegagalan,
pastikan dulu kegagalan itu bukan buatan sendiri.

### G4. Variabel lokal menimpa parameter

**Gejala.** Variabel lokal `judul` di dalam fungsi menimpa parameter `judul`.
Semua bagian memakai judul yang sama.

**Aturan.** Tertangkap karena luarannya **dibaca**, bukan diasumsikan. Baca
hasilnya.

### G5. Query string sudah diratakan

**Gejala.** `q.get("project", [""])[0]` mengambil **huruf pertama** nama proyek,
karena `q` sudah berupa string, bukan daftar. Endpoint diam-diam menjawab
"tidak ditemukan".

**Aturan.** Periksa bentuk data di tempat ia dibuat, bukan dari kebiasaan
pustaka lain. Dan kunci bug yang sudah diperbaiki dengan uji.

---

## H. Cara bekerja yang mencegah sebagian besar di atas

1. **Ukur, jangan asumsikan.** "37% blok kode tanpa bahasa", "31 berkas
   ditampilkan tapi tidak diserahkan", "pesan terakhir 4014 karakter dari batas
   3900" — angka yang menemukan bug, bukan pembacaan kode.
2. **Baca luaran yang kamu hasilkan.** Render, buka, hitung.
3. **Uji di objek sekali pakai, hapus di `finally`, verifikasi sesudahnya.**
4. **Setiap bug yang diperbaiki dapat satu uji.** Uji itu menyebut gejalanya di
   komentar, supaya pembaca berikutnya tahu kenapa ia ada.
5. **Jangan melonggarkan uji yang menangkapmu.** Saat uji lama menolak hasil
   kerjaku karena lewat 7 karakter, yang salah adalah kodenya, bukan ujinya.
6. **Laporkan apa adanya.** Kalau pemeriksaan pertama tidak membuktikan apa-apa
   (mis. `curl` hanya mendapat halaman login), katakan itu dan ulangi dengan
   benar.
