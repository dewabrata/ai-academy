# Proposal

## Why

Uji perbandingan `perkuat-agen-materi` (22 Sep 2026) menunjukkan bahwa contoh
✓/❌ dan cek mandiri di prompt tidak menaikkan mutu materi. Dinilai oleh Reviewer
yang sama, baseline mendapat LULUS/LULUS/TOLAK dan versi baru mendapat
TOLAK/PERLU-REVISI/TOLAK. Kedua versi gagal dengan pola yang sama: berkas dalam
satu pertemuan saling bertentangan (slide vs modul, kunci vs lab). Penyebabnya
ada di desain alur, bukan di prompt. Writer, Slide, dan Lab berjalan paralel,
jadi tidak satu pun membaca hasil yang lain.

Alur ini juga tidak sesuai dengan cara pemilik proyek bekerja. Pemilik proyek
tidak menulis satu pertemuan sekaligus. Ia memecah pertemuan menjadi point (±10
per pertemuan, 10–20 halaman per point), menuntaskan tiap point lewat loop
Writer → Reviewer + Fact-Checker, dan baru membangun dokumen, slide, dan tugas
setelah semua point dalam pertemuan itu jadi.

Uji yang sama juga menemukan dua bug. Pertama, `allowed_tools` hanya menyetujui
tool secara otomatis dan tidak membatasinya, sehingga Reviewer masih bisa
menjalankan Bash. Kedua, pada putaran telaah pertama Reviewer berjalan sebelum
pemeriksa otomatis, padahal promptnya merujuk `docs/PEMERIKSAAN.md`.

## What Changes

- **BREAKING — alur produksi per point.** Tahap `pilot`, `produksi`, dan
  `telaah` diganti oleh:
  - tahap `produksi` yang mengerjakan pertemuan satu per satu, dan di dalamnya
    point satu per satu;
  - tahap `akhir` yang menjalankan Editor.

  Tiap point melewati loop Writer → Reviewer + Fact-Checker (paralel) → revisi,
  paling banyak 3 putaran. Point yang belum siap setelah 3 putaran dieskalasi
  ke gate pertemuan.
- **Pilot di point pertama.** Setelah point 1 pertemuan pilot lolos loop,
  pipeline berhenti supaya pemilik proyek memeriksa gayanya sebelum point
  berikutnya ditulis.
- **Paket pertemuan dibangun dari point yang sudah final.** Paket berisi:
  - `HANDBOOK.md`, gabungan semua point yang digabung deterministik tanpa
    ditulis ulang;
  - `SLIDE.md` dengan catatan trainer;
  - tugas: latihan dan kunci, praktik langkah demi langkah dan/atau lab kode
    sesuai tanda di blueprint;
  - `QUIZ_AIKEN.txt` berisi 10 soal pilihan ganda untuk Moodle.

  Paket lalu ditelaah konsistensinya terhadap point. Pemeriksa otomatis
  dijalankan **sebelum** telaah paket.
- **Gate per pertemuan.** Gate ini menampilkan skor pemeriksa, point yang
  dieskalasi, dan semua pertanyaan "Perlu dicek-ditanyakan" dari Reviewer yang
  terkumpul selama pertemuan itu.
- **Peran baru Fact-Checker.** Fact-Checker memverifikasi klaim bertanda
  `[CEK-FAKTA: ...]` dan klaim produk lain ke dokumentasi resmi lewat web.
  Writer juga boleh memakai web.
- **Reviewer memakai format dan 7 lensa pemilik proyek.** Formatnya
  `Revisi / Perlu dicek-ditanyakan / Sudah oke lanjut / Status`. Skor 1–4
  dicatat tersembunyi hanya untuk pengukuran.
- **Peran Lab menjadi Tugas.** Peran ini menulis latihan, kunci, praktik, lab
  kode, dan quiz AIKEN.
- **Gaya pemilik proyek masuk `_standar.md`** sebagai aturan global. Aturan khusus
  klien dibawa per proyek lewat `--klien <berkas>` dan disimpan sebagai
  `docs/KLIEN.md`.
- **Perbaikan bug:**
  - daftar tool peran dibatasi dengan opsi SDK `tools=`;
  - pemeriksa berjalan sebelum telaah.
- **Pemeriksa diperbarui** untuk luaran baru:
  - status point;
  - format AIKEN;
  - sisa penanda `[CEK-FAKTA`;
  - kelengkapan paket.

## Capabilities

### New Capabilities

- `produksi-per-point`: loop penulisan per point, pilot di point pertama, dan
  eskalasi.
- `paket-pertemuan`: pembangunan handbook, slide, tugas, dan quiz dari point
  final, telaah konsistensi paket, serta gate pertemuan.
- `verifikasi-fakta`: peran Fact-Checker dan penanda klaim.

### Modified Capabilities

Tidak ada. Spec change sebelumnya belum diarsipkan, jadi kebutuhan baru ditulis
sebagai kapabilitas baru.

## Impact

- `academy.py`: tahap dan orkestrasi ditulis ulang untuk bagian produksi.
  Kurikulum dan Blueprint tetap sama.
- `roles.py`: peran FAKTA dan TUGAS ditambahkan, dan opsi `tools` diberlakukan.
- `prompts/`:
  - `writer.md`, `reviewer.md`, dan `blueprint.md` ditulis ulang;
  - `fakta.md` dan `tugas.md` ditambahkan, menggantikan `lab.md`;
  - `slide.md` dan `_standar.md` disesuaikan.
- `pemeriksa.py`, `exporter.py` (handbook, AIKEN), `uji/uji_asap.py`,
  `control.py`, `dashboard.py`: disesuaikan dengan nama tahap dan luaran baru.
- Biaya: dengan semua Opus, satu pertemuan (10 point × 10–20 halaman × hingga 3
  putaran) jauh lebih mahal daripada alur lama. Plafon `BUDGET_PROYEK` perlu
  dinaikkan untuk produksi nyata. Uji memakai Sonnet dan point pendek
  (`POINT_HALAMAN`).
