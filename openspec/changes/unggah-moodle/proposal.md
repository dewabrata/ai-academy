# Proposal

## Why

Materi yang sudah selesai diproduksi masih harus dipasang ke LMS satu per satu
lewat antarmuka Moodle: membuat kursus, mengunggah enam berkas per pertemuan,
membuat quiz dan mengetik ulang sepuluh soalnya, membuat tugas, menyusun
gradebook. Untuk pelatihan empat hari itu pekerjaan berjam-jam yang seluruhnya
mekanis, dan tiap pengulangan membuka peluang salah tempat.

Moodle core tidak menyediakan jalan otomatis. Diuji pada LMS Juara Coding
(Moodle 5.2, 799 fungsi web service terdaftar): `core_courseformat_new_module`
menolak dua belas jenis modul dengan "does not support quick creation", dan
`core_files_upload` ke area modul mengembalikan `codingerror`. Berkas bisa
sampai ke Moodle, tetapi berhenti di area draft yang tidak terlihat peserta.

Dengan plugin MoodlIA terpasang (251 fungsi tambahan), seluruh jalur menjadi
mungkin dan sudah dibuktikan ujung-ke-ujung di kursus percobaan.

## What Changes

- Peran baru **MOODLE** menyusun rencana unggah ke `docs/MOODLE.json`: nama
  kursus, judul section, instruksi tiap tugas, pertanyaan feedback per hari,
  dan bobot penilaian beserta alasannya. Peran ini tidak menyentuh LMS.
- `moodle.py` — klien MCP dengan daftar putih tool; daftar tool disimpan ke
  berkas karena `tools/list` berukuran besar dan lambat.
- `moodle_unggah.py` — memeriksa rencana lalu mengeksekusinya. Tanpa model,
  sehingga unggahan yang sama menghasilkan kursus yang sama.
- `aiken.py` — mengurai AIKEN, dan menghasilkan Moodle XML untuk impor manual.
- Tab **Moodle** di dashboard: meninjau rencana, menyunting nama dan bobot,
  lalu mengunggah.
- Perintah `--moodle rencana|rencana-ulang` di `academy.py`.

## Impact

- Baru: `moodle.py`, `moodle_unggah.py`, `aiken.py`, `prompts/moodle.md`
- Diubah: `roles.py`, `academy.py`, `control.py`, `dashboard.py`, `setelan.py`
- Butuh plugin MoodlIA di Moodle. `python moodle.py` melaporkan fungsi yang
  belum ada sebelum unggahan dimulai.
- Fitur ini opsional dan terpisah: pipeline produksi materi tidak berubah, dan
  Moodle yang bermasalah tidak menghentikan produksi.
