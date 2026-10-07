# template_agent — pola membangun aplikasi agentic yang tahan lama

Dokumen ini ditulis **untuk Claude di sesi baru**, bukan untuk dibaca manusia
sebagai cerita. Isinya aturan: lakukan ini, jangan itu, dan alasannya — yang
hampir selalu berupa kejadian nyata di `ai-academy`.

Cara memakainya: salin folder `template_agent/` ke repo baru, lalu di pesan
pertama katakan *"ikuti pola di template_agent/"*. Jangan menyalin kode
`ai-academy` apa adanya; yang dipakai ulang adalah **bentuk keputusannya**.

## Peta berkas

| Berkas | Isi |
|---|---|
| [arsitektur.md](arsitektur.md) | Konsep agentic: peran, loop, gate manusia, plafon biaya, lock, resume, pemeriksa deterministik |
| [monitoring.md](monitoring.md) | Memantau proses yang berjalan berjam-jam: event log, snapshot status, dua pintu jawaban |
| [integrasi.md](integrasi.md) | Menyentuh sistem luar (LMS, API, MCP) tanpa merusaknya |
| [jebakan.md](jebakan.md) | Katalog kesalahan nyata beserta akar masalah dan pencegahannya |
| [konvensi.md](konvensi.md) | Penamaan, komentar, pola uji, deploy, verifikasi |

## Dua belas aturan inti

Kalau hanya sempat membaca satu halaman, baca yang ini.

1. **Agen mengambil keputusan, kode biasa yang mengeksekusi.** Model menulis
   rencana (JSON/Markdown); Python yang memvalidasi dan menjalankannya. Setiap
   langkah mekanis yang diserahkan ke model adalah biaya dan ketidakpastian
   yang tidak perlu.

2. **Satu peran = satu `query()` tersendiri** dengan system prompt, model, dan
   daftar tool miliknya. Konteks tiap peran bersih, biayanya terukur, dan
   kegagalan satu peran tidak mencemari yang lain.

3. **Batasi tool lewat `tools=`, bukan `allowed_tools=`.** `allowed_tools` hanya
   menyetujui otomatis — peran tetap bisa memakai tool lain. `tools=` yang
   benar-benar menentukan apa yang tersedia.

4. **Tegakkan aturan dengan hook, bukan dengan kalimat di prompt.** "Jangan
   menulis di luar foldermu" yang hanya ada di prompt baru ketahuan dilanggar
   setelah semuanya jadi — tempat termahal untuk memperbaikinya.

5. **Setiap tahap punya plafon biaya.** `max_budget_usd` per tahap, plus plafon
   total proyek. Tanpa itu satu loop yang ngotot bisa menghabiskan puluhan dolar
   tanpa ada yang menyadari.

6. **Gate manusia di titik yang mahal untuk salah**, bukan di setiap langkah.
   Taruh gate sesudah perencanaan (sebelum produksi) dan sesudah tiap satuan
   besar — di situlah kesalahan paling murah diperbaiki.

7. **Keadaan ada di berkas, bukan di memori proses.** `STATE.txt`, `status.json`,
   `events.jsonl`, `<proyek>.lock`. Proses boleh mati kapan saja; yang tidak
   boleh hilang adalah tempat ia berhenti.

8. **Pemeriksa deterministik mendahului telaah model.** Hal yang bisa dihitung
   — jumlah butir, berkas yang dirujuk tapi tidak ada, sintaks — diperiksa kode
   biasa, gratis dan pasti. Model hanya menilai yang memang butuh penilaian.

9. **Daftar putih untuk tool yang menyentuh sistem luar, dan tanpa satu pun
   fungsi penghapus.** Token biasanya milik admin; satu kesalahan mengenai
   seluruh sistem.

10. **Periksa-lalu-buat harus satu langkah berkunci.** Dua permintaan yang
    berbarengan sama-sama melihat "belum ada" dan sama-sama membuat.

11. **Setiap proses yang lambat harus terlihat sedang bekerja.** Tanpa tanda,
    tombolnya ditekan dua kali — dan di operasi yang membuat sesuatu, itu
    berarti dua objek.

12. **Proses yang sudah berjalan memegang kode yang dimuat saat ia start.**
    Perbaikan di tengah run tidak berlaku untuk run itu. Selalu katakan ini
    saat melaporkan perbaikan atas sesuatu yang sedang berjalan.

## Teknologi yang dipakai dan kenapa

| Lapis | Pilihan | Alasan |
|---|---|---|
| Orkestrasi agen | Claude Agent SDK (Python), `query()` per tahap | Kontrol penuh atas tool, hook, budget, dan resume per peran |
| Penegakan aturan | Hook `PreToolUse` / `PostToolUse` milik SDK | Menolak saat kejadian, dan penolakannya tercatat |
| Keadaan | Berkas datar di `docs/` | Bisa dibaca proses lain, selamat dari proses mati, mudah diperiksa manusia |
| Control plane | HTTP server stdlib + Telegram Bot API | Tanpa framework; dua pintu ke gate yang sama |
| Sistem luar | MCP over HTTP JSON-RPC | Satu pintu, satu daftar putih, mudah diuji |
| Dokumen | python-docx / python-pptx / openpyxl | Murni Python, jalan di server tanpa Office |
| Deploy | systemd **user** service | Tidak menyentuh konfigurasi sistem yang dipakai aplikasi lain |

Rinciannya ada di berkas lain. Mulai dari [arsitektur.md](arsitektur.md).
