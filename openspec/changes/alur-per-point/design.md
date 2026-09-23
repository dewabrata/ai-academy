# Design

## Context

Hasil uji `perkuat-agen-materi` dan alur kerja pemilik proyek sudah dirangkum di
`proposal.md`. Keputusan pemilik proyek (22 Sep 2026):

| Hal | Keputusan |
|---|---|
| Unit kerja | point dari silabus pemilik, 10–20 halaman, ditulis berurutan |
| Persetujuan | per pertemuan, setelah semua point jadi; pilot di point pertama |
| Loop | Writer → Reviewer + Fact-Checker, maks. 3 putaran, lewat orkestrasi Python (bukan Agent Teams) |
| Web | Writer dan Fact-Checker |
| Review | format dan 7 lensa pemilik + skor 1–4 tersembunyi |
| Pertanyaan ambigu | Writer lanjut dengan asumsi eksplisit; pertanyaan dikumpulkan ke gate pertemuan |
| Doc | handbook = gabungan semua point |
| Tugas | latihan + kunci, praktik langkah demi langkah, lab kode, quiz 10 soal AIKEN per pertemuan |
| Jenis tugas | dari tanda di silabus; kalau tidak ada, Blueprint yang memilih |
| Slide | slide mengajar + catatan trainer |
| Gaya | global di `_standar.md`, khusus klien per proyek |
| Model | semua Opus untuk produksi; uji memakai Sonnet |

## Goals / Non-Goals

**Goals:**

- Point ditulis dan ditelaah satu per satu, dengan konteks point sebelumnya.
- Slide, tugas, dan quiz dibangun dari isi point yang sudah final, sehingga
  tidak bisa bertentangan dengan isi yang belum ada.
- Pemilik proyek memeriksa gaya sebelum biaya besar keluar (pilot point), dan
  memeriksa hasil sekali per pertemuan.

**Non-Goals:**

- Agent Teams. Loop ditiru di Python supaya bisa berjalan tanpa ditunggui,
  terukur biayanya, dan bisa di-resume.
- Parser langsung untuk format silabus pemilik. Lihat D1.
- Point paralel dalam satu pertemuan atau pertemuan paralel. Lihat D3.

## Decisions

### D1. Daftar point dibaca dari BLUEPRINT, bukan dari silabus

Silabus datang dalam berbagai bentuk (md, docx, pdf). Peran Blueprint menyalin
point dari silabus **apa adanya** ke bagian `### Point` yang formatnya pasti:

```
### Point
1. <judul point persis seperti di silabus> — P1-1, P1-2
2. ...

### Tugas
Jenis: praktik | lab-kode | praktik+lab-kode
```

Python hanya mengurai format ini. Pemilik proyek melihat daftar point di gate
Blueprint, sehingga salah salin tertangkap sebelum produksi. Blueprint dilarang
menggabung, memecah, atau menambah point kecuali silabus tidak punya point sama
sekali. Dalam kasus itu Blueprint menyusunnya dan menyebutnya di KESENJANGAN.

### D2. Status loop dibaca dari baris status, bukan dari penilaian model atas model

Setiap putaran menghasilkan dua berkas di `materi/pertemuan-NN/review/`:

- `point-KK-review-rR.md`, diakhiri `Status: Siap ditunjukkan ke user` atau
  `Status: Perlu revisi`;
- `point-KK-fakta-rR.md`, diakhiri `Status: Tidak ada koreksi` atau
  `Status: Ada koreksi`.

Python mencocokkan baris itu. Point dianggap siap hanya jika keduanya
menyatakan siap. Berkas status yang tidak ada atau tidak terurai dihitung
"belum siap", karena lebih aman satu putaran berlebih daripada point cacat
lolos.

Skor tersembunyi ditulis Reviewer sebagai komentar HTML
`<!-- SKOR akurasi=N capaian=N keterbacaan=N koherensi=N -->`, sehingga tidak
tampil di catatan revisi dan tidak mengubah gaya catatannya.

### D3. Point berurutan, pertemuan berurutan

Point k membaca point k-1 secara utuh dan judul point sebelumnya supaya studi
kasus mengalir, sesuai prinsip "satu studi kasus utuh lebih baik daripada
banyak contoh dangkal". Paralel antarpertemuan akan memutus kesinambungan itu
dan membuat beberapa gate pertemuan mengantre sekaligus. Yang diparalelkan
hanya Reviewer + Fact-Checker dalam satu putaran, dan Slide + Tugas saat
membangun paket.

### D4. Eskalasi tidak menghentikan pipeline

Sesuai keputusan "kumpulkan, tanya di akhir pertemuan", point yang belum siap
setelah 3 putaran ditandai `eskalasi`, dan pipeline lanjut ke point berikutnya.
Point itu tampil paling atas di gate pertemuan beserta catatan terakhirnya.
Pengecualiannya pilot: point pilot yang belum siap tetap dibawa ke gate pilot,
karena gate itu yang menentukan gaya.

### D5. Handbook digabung Python

"Handbook = gabungan semua point" berarti isi point tidak ditulis ulang.
Penggabungan deterministik (judul, daftar isi, point berurutan) tidak
membutuhkan model, tidak berisiko mengubah isi yang sudah lolos telaah, dan
tidak memakan biaya.

### D6. Telaah paket setelah pemeriksa

Urutan setelah point selesai:

```
Slide + Tugas → gabung handbook → ekspor → pemeriksa → telaah paket → gate
```

Pemeriksa berjalan sebelum telaah paket supaya Reviewer bisa membaca
`PEMERIKSAAN.md`. Ini memperbaiki bug urutan. Telaah paket hanya memeriksa
konsistensi slide, tugas, dan quiz terhadap point, bukan isi point lagi.

Paket yang "Perlu revisi" diperbaiki satu kali oleh pemilik berkasnya. Setelah
itu hasilnya dibawa ke gate.

### D7. Tool dibatasi dengan `tools=`

`ClaudeAgentOptions.tools` menjadi daftar tool yang tersedia, dan
`allowed_tools` hanya persetujuan otomatis. Keduanya diisi daftar yang sama,
sehingga peran benar-benar tidak punya tool di luar daftarnya.

| Peran | Tool |
|---|---|
| Kurikulum, Blueprint, Reviewer, Slide, Editor | Read, Write, Edit, Glob, Grep |
| Writer, Fact-Checker | + WebSearch, WebFetch |
| Tugas | + Bash |

### D8. Wilayah tulis

| Tahap | Wilayah |
|---|---|
| WRITER-NN.KK | `materi/pertemuan-NN/point/` |
| REVIEWER-NN.KK, FAKTA-NN.KK, PAKET-NN | `materi/pertemuan-NN/review/` |
| SLIDE-NN, TUGAS-NN | `materi/pertemuan-NN/` |
| Kurikulum, Blueprint | `docs/` |
| Editor | ruang kerja |

### D9. Panjang point bisa diatur

`POINT_HALAMAN` (bawaan `10–20`) masuk ke prompt Writer. Uji memakai `1–2`
supaya satu uji tidak menghabiskan kuota.

## Risks / Trade-offs

- **Biaya Opus besar.** Hitungannya 10 point × (Writer + Reviewer + Fact-Checker)
  × rata-rata 1,5 putaran per pertemuan. Mitigasinya: plafon per peran
  (`BUDGET_POINT_*`), plafon proyek, dan pilot point yang menghentikan gaya yang
  meleset sejak point pertama.
- **Point panjang melebihi satu keluaran model.** Writer diminta menulis per
  bagian (tulis, lalu tambah dengan Edit), bukan satu Write raksasa.
- **Konteks point sebelumnya membengkak.** Hanya point k-1 yang dibaca utuh,
  sedangkan point sebelumnya cukup judul dan subjudulnya.
- **Web membuat hasil kurang dapat diulang.** Ini diterima demi fakta produk
  yang terbaru. Fact-Checker wajib menyebut URL sumber tiap klaim.

## Migration Plan

Proyek lama dengan `STATE.txt` bernilai `pilot`, `produksi`, atau `telaah`
dipetakan ke `produksi`. Folder pertemuan lama tanpa `point/` dianggap belum
diproduksi dengan alur baru. Tidak ada konversi otomatis.
