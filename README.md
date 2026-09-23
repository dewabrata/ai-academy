# AI Academy — produksi materi ajar dari silabus

Beri satu silabus yang sudah dipecah menjadi point. Dapatkan handbook, deck
presentasi dengan catatan trainer, latihan berkunci, praktik atau lab kode, dan
quiz siap impor Moodle — untuk setiap pertemuan.

Materi ditulis **per point**, satu per satu, bukan satu pertemuan sekaligus.
Tiap point ditulis, ditelaah, dan diverifikasi faktanya sampai tuntas sebelum
point berikutnya dimulai. Slide, tugas, dan quiz baru dibangun setelah semua
point dalam satu pertemuan jadi — sehingga tidak bisa bertentangan dengan isi
yang belum ada.

Dibangun di atas Claude Agent SDK (Python): tiap tahap adalah satu `query()`
terpisah, jadi konteks tiap peran bersih dan biaya per tahap bisa dibatasi.

Perencanaannya dikerjakan dengan [OpenSpec](https://github.com/Fission-AI/OpenSpec)
(spec-driven development) — lihat [Perencanaan](#perencanaan-openspec).

## Pipeline

```
silabus (.md / .txt / .docx / .pdf, atau teks langsung)
  │
  ├─ KURIKULUM   capaian belajar, level peserta, peta pertemuan, glosarium  [gate]
  │
  ├─ BLUEPRINT   point per pertemuan (disalin dari silabus), jenis tugas,
  │              alur sesi, logistik trainer                                [gate]
  │
  └─ PRODUKSI    pertemuan satu per satu; di dalamnya point satu per satu:
       │
       │   WRITER  ──→  point-NN.md
       │      ↑            │
       │      │            ├─→ REVIEWER      catatan revisi + skor tersembunyi
       │      │            └─→ FACT-CHECKER  klaim produk diverifikasi ke web
       │      └──── revisi ──┘   maks. 3 putaran, lalu dieskalasi
       │
       │   (point 1 pertemuan pilot)                                        [gate PILOT]
       │
       │   setelah semua point siap, paket dibangun dari point final:
       │      SLIDE   → SLIDE.md + catatan trainer → SLIDE.pptx
       │      TUGAS   → LATIHAN.md, KUNCI.md, QUIZ_AIKEN.txt,
       │                PRAKTIK.md dan/atau lab/ (solusi dieksekusi)
       │      HANDBOOK.md  ← gabungan semua point (digabung Python)
       │      → ekspor → pemeriksa otomatis → telaah paket → satu revisi
       │                                                              [gate PERTEMUAN-n]
       │
       └─ AKHIR      EDITOR menyeragamkan istilah, ekspor ulang, ringkasan
```

Di setiap gate, ketik `y` (setuju), tulis masukan (materi direvisi lalu ditanya
lagi), atau `q` (berhenti — pekerjaan tetap tersimpan).

**Gate PILOT adalah yang paling penting.** Gaya, kedalaman, dan nada paling
sulit dijelaskan lewat prompt dan paling mahal kalau salah. Gate ini berhenti
setelah **point pertama** selesai, jadi kalau gayanya meleset yang terbuang
hanya satu point. Masukan Anda disimpan sebagai `docs/ACUAN_GAYA.md` dan
berlaku untuk semua point berikutnya.

**Gate PERTEMUAN-n** menampilkan skor pemeriksa otomatis, point yang
dieskalasi, dan semua pertanyaan yang dikumpulkan Reviewer dan Writer selama
pertemuan itu.

## Delapan peran

| Peran | Tool | Luaran |
|---|---|---|
| **Kurikulum** | baca/tulis | `KURIKULUM.md`, `GLOSARIUM.md` — capaian terukur, level peserta disimpulkan dari silabus, kesenjangan silabus |
| **Blueprint** | baca/tulis | `BLUEPRINT.md` — daftar point per pertemuan (disalin apa adanya dari silabus), jenis tugas, alur sesi, logistik trainer. Ini kontrak produksi |
| **Writer** | baca/tulis + **web** | `point/point-NN.md` — satu point sedalam handbook, plus catatan asumsi dan pertanyaan |
| **Reviewer** | baca/tulis | catatan revisi per point dan per paket, format `Revisi / Perlu dicek-ditanyakan / Sudah oke lanjut / Status` |
| **Fact-Checker** | baca/tulis + **web** | verifikasi klaim produk ke dokumentasi resmi, satu baris per klaim beserta URL sumbernya |
| **Slide** | baca/tulis | `SLIDE.md` dari point final, tunduk batas kepadatan, logistik di catatan pengajar |
| **Tugas** | baca/tulis + **Bash** | `LATIHAN.md`, `KUNCI.md`, `QUIZ_AIKEN.txt`, `PRAKTIK.md`, `lab/`. Solusi lab **wajib dieksekusi sampai lulus** |
| **Editor** | baca/tulis | `GLOSARIUM.md` gabungan, `TELAAH_BAHASA.md`, penyeragaman istilah |

Peran Tugas satu-satunya yang punya akses `Bash`, dan hanya Writer serta
Fact-Checker yang punya akses web. Daftar tool tiap peran ditegakkan lewat opsi
SDK `tools=`, jadi peran benar-benar tidak punya tool di luar daftarnya.

## Cara kerja loop per point

1. **Writer** menulis satu point sesuai arah isi di blueprint, dengan panjang
   target `POINT_HALAMAN` (bawaan 10–20 halaman). Klaim tentang produk ditandai
   `[CEK-FAKTA: ...]`, bukan diklaim benar sendiri.
2. **Reviewer** dan **Fact-Checker** menelaah bersamaan. Keduanya mengakhiri
   catatannya dengan baris `Status:` yang dibaca mesin.
3. Kalau salah satu belum bersih, Writer merevisi dan keduanya menelaah ulang.
   Maksimal `POINT_MAKS_PUTARAN` putaran (bawaan 3).
4. Point yang belum siap setelah batas itu ditandai **eskalasi**, dan pipeline
   lanjut ke point berikutnya. Point tersebut ditampilkan paling atas di gate
   pertemuan.

Pertanyaan yang muncul di tengah jalan tidak menghentikan pipeline. Writer
melanjutkan dengan asumsi yang ditulis eksplisit, dan semua pertanyaan
dikumpulkan ke `PERTANYAAN.md` untuk dijawab sekali di gate pertemuan.

## Pemeriksa otomatis

`pemeriksa.py` memberi skor per pertemuan tanpa memanggil model sama sekali:
paket lengkap sesuai jenis tugas, semua point siap, tidak ada penanda
`[CEK-FAKTA` tersisa, capaian tertutup dan teruji, soal bertanda capaian,
lembar latihan bebas jawaban, quiz AIKEN bisa diimpor Moodle, alokasi waktu
blueprint pas, slide sesuai batas, dan solusi lab jalan.

```bash
python pemeriksa.py workspace/<proyek>
python pemeriksa.py --bandingkan workspace/proyek-a workspace/proyek-b
```

Hasilnya ditulis ke `docs/PEMERIKSAAN.md` dan ditampilkan di gate pertemuan.

## Struktur

```
ai-academy/
├── academy.py       orchestrator / pipeline
├── rencana.py       membaca point & jenis tugas dari BLUEPRINT.md
├── silabus.py       intake: .md/.txt/.docx/.pdf → satu teks ternormalisasi
├── roles.py         definisi delapan peran (model, tool, pemilik berkas)
├── exporter.py      Markdown → DOCX & PPTX, penggabung handbook, batas slide
├── pemeriksa.py     pemeriksaan deterministik tanpa model
├── hooks_sdk.py     penegakan saat penulisan (wilayah, biner, kepadatan slide)
├── monitor.py       event log, status, Telegram, gate tiga kanal
├── dashboard.py     panel kendali web lokal
├── control.py       menjalankan academy.py dari dashboard/Telegram
├── opsi.py          opsi luaran per proyek (docs/OPSI.json)
├── setelan.py       baca/tulis .env untuk halaman Pengaturan
├── prompts/*.md     system prompt per peran — ubah perilaku di sini, bukan di kode
├── prompts/_standar.md   standar & gaya, otomatis menempel ke semua peran
├── contoh/          silabus contoh dan konteks klien contoh
├── uji/uji_asap.py  uji asap dengan jawaban gate dipatok
├── openspec/        spesifikasi & rencana (OpenSpec)
└── workspace/<proyek>/
    ├── sumber/      silabus asli + silabus.txt (teks yang dibaca peran)
    ├── docs/        KURIKULUM, GLOSARIUM, BLUEPRINT, KLIEN, ACUAN_GAYA,
    │                PEMERIKSAAN, TELAAH_BAHASA, PRODUKSI.json (status point),
    │                OPSI.json (opsi luaran), events.jsonl, status.json
    └── materi/pertemuan-NN/
        ├── point/point-NN.md          isi materi, sumber kebenaran
        ├── point/point-NN.catatan.md  asumsi & pertanyaan Writer
        ├── review/                    catatan Reviewer & Fact-Checker per putaran
        ├── HANDBOOK.md  → HANDBOOK.docx    (gabungan semua point)
        ├── SLIDE.md     → SLIDE.pptx
        ├── LATIHAN.md   → LATIHAN.docx,  KUNCI.md → KUNCI.docx
        ├── PRAKTIK.md   → PRAKTIK.docx      (jenis tugas praktik)
        ├── lab/{README.md, awal/, solusi/}  (jenis tugas lab-kode)
        ├── QUIZ_AIKEN.txt                    10 soal, siap impor Moodle
        ├── PERTANYAAN.md, PROSES.md
        └── MASUKAN.md                        masukan Anda di gate pertemuan
```

Berkas biner **selalu** turunan dari sumber Markdown, dan `HANDBOOK.md` selalu
turunan dari berkas point. Peran AI tidak pernah menulis `.docx`/`.pptx`
langsung.

## Setup

```bash
# 1. Claude Code CLI (kalau belum)
npm i -g @anthropic-ai/claude-code

# 2. Python env
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt

# 3. Konfigurasi
copy .env.example .env          # Windows
# cp .env.example .env
# Pakai langganan Claude (Pro/Max): biarkan ANTHROPIC_API_KEY kosong,
#   pastikan sudah `claude` -> /login
# Pakai API key: isi ANTHROPIC_API_KEY
```

## Jalankan

```bash
# Dari berkas silabus
python academy.py contoh/silabus-point.md

# Dengan konteks klien (industri, audiens, aturan gaya khusus)
python academy.py silabus.docx --klien contoh/klien-contoh.md

# Nama proyek sendiri, dan pertemuan 3 yang point pertamanya jadi pilot
python academy.py silabus.docx --project otomasi-data --pilot 3

# Lanjutkan proyek yang berhenti
python academy.py --project otomasi-data --resume produksi

# Buat slide menyusul (proyek yang dibuat tanpa slide)
python academy.py --project otomasi-data --slide semua
python academy.py --project otomasi-data --slide 3
```

Tahap yang bisa dipakai `--resume`: `kurikulum`, `blueprint`, `produksi`,
`akhir`. Point yang sudah siap atau dieskalasi tidak ditulis ulang, dan
pertemuan yang gate-nya sudah disetujui dilewati.

**Silabus Anda sebaiknya sudah memuat point per pertemuan.** Blueprint menyalin
point itu apa adanya; ia hanya menyusun sendiri kalau silabus tidak menyebut
point sama sekali, dan akan melaporkannya sebagai kesenjangan. Daftar point yang
dibaca Python ditampilkan di gate Blueprint, jadi salah salin tertangkap sebelum
biaya produksi keluar.

Uji asap sebelum memakai silabus penuh — contoh berikut hanya 2 pertemuan × 2
point, memakai Sonnet dan point pendek supaya hemat:

```bash
python uji/uji_asap.py contoh/silabus-point.md --project uji-asap --klien contoh/klien-contoh.md
```

## Kalau pipeline berhenti

```bash
python control.py status <proyek>
```

Perintah ini menyebut keadaannya — berjalan, menunggu gate, kunci basi, atau
berhenti — beserta perintah pemulihannya. Proses yang mati tidak menghilangkan
pekerjaan: `python control.py lanjut <proyek>` menyambung dari point terakhir.
Rinciannya di [MANUAL.md §9](MANUAL.md).

## Dashboard

```bash
python dashboard.py     # http://127.0.0.1:8770
```

Isi dashboard:

| Bagian | Isi |
|---|---|
| **Proyek** | Daftar semua proyek: tahap, jumlah pertemuan, biaya, waktu diubah, dan status. Aksi per proyek: Buka, Ganti nama, Duplikat setelan, Arsipkan. Di bawahnya tabel **Arsip** dengan Pulihkan dan Hapus permanen |
| **Proyek baru** | Satu layar: seret-lepas silabus (atau tempel teksnya), konteks klien, nama proyek, pertemuan pilot, panjang point, maks. putaran, model, pilihan slide dan ekspor, serta preset **mutu maksimal** (tanpa plafon biaya) |
| **Ringkasan** | Gate yang menunggu beserta pertanyaannya utuh, kemajuan per point (siap / proses / eskalasi), biaya, kuota, dan aktivitas |
| **Materi** | Unduh **semua materi sebagai .zip** (atau per pertemuan), unduhan per berkas, tombol **Buat slide** untuk pertemuan yang belum punya slide, dan pembaca untuk point, handbook, serta catatan Reviewer dan Fact-Checker |
| **Berkas & opsi** | Unggah dan hapus silabus, unggah atau hapus konteks klien, dan mengubah opsi produksi proyek yang sudah ada |
| **Pengaturan** | Menyunting `.env` dari UI: Telegram (dengan tombol kirim pesan uji), model, plafon, setelan point, dan akun dashboard |

**Menghapus proyek** dilakukan dua langkah. Tombol **Arsipkan** memindahkan
proyek ke `workspace/.arsip/<nama>-<waktu>` tanpa menghapus apa pun, dan bisa
dipulihkan. Menghapus permanen hanya bisa dari tabel Arsip, dan menuntut nama
arsipnya diketik persis. Keduanya ditolak selama pipeline proyek itu berjalan.

Selama `DASHBOARD_PASS` kosong, dashboard dipakai tanpa login dan hanya melayani
`127.0.0.1`. Begitu diisi — lewat `.env` atau halaman Pengaturan — dashboard
meminta nama pengguna dan kata sandi, lalu menyimpan sesi di cookie.

Terikat `127.0.0.1` secara bawaan dan itu disengaja: panel ini menjalankan
pipeline, dan peran Tugas di dalamnya punya akses `Bash`. Kalau
`DASHBOARD_HOST` diisi alamat non-lokal sementara `DASHBOARD_PASS` kosong, panel
**menolak jalan**. Akses jauh paling aman tanpa membuka port:

```bash
ssh -L 8770:127.0.0.1:8770 user@server
```

## Telegram (opsional)

Isi `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` di `.env`. Anda akan menerima
notifikasi tiap tahap dan bisa menjawab gate dari HP. Perintah saat tidak ada
pipeline berjalan: `/status`, `/daftar`, `/proyek <nama>`, `/lanjut`,
`/resume <tahap>`, `/stop`.

Gate bisa dijawab dari tiga kanal — terminal, dashboard, Telegram — dan yang
tiba lebih dulu yang dipakai.

## Biaya

Semua peran memakai **opus** secara bawaan. Alur per point jauh lebih mahal
daripada satu tulisan per pertemuan: satu pertemuan berisi 10 point × (Writer +
Reviewer + Fact-Checker) × rata-rata 1,5 putaran. Plafon di `.env`:

| Variabel | Untuk |
|---|---|
| `BUDGET_KURIKULUM`, `BUDGET_BLUEPRINT` | tahap perencanaan |
| `BUDGET_POINT_WRITER` | **per point, per putaran** |
| `BUDGET_POINT_REVIEW`, `BUDGET_POINT_FAKTA` | telaah per point, per putaran |
| `BUDGET_SLIDE`, `BUDGET_TUGAS`, `BUDGET_PAKET_REVIEW` | paket per pertemuan |
| `BUDGET_EDITOR` | tahap akhir |
| `BUDGET_PROYEK` | plafon total; kalau terlampaui, pipeline bertanya |

Semua plafon tahap: `0` atau kosong berarti **tanpa batas**. Preset "mutu
maksimal" di layar buat proyek memakai itu, dan membiarkan pipeline menunggu
reset kuota lalu melanjutkan sendiri.

`POINT_HALAMAN` dan `POINT_MAKS_PUTARAN` adalah dua pengatur biaya terbesar.
Biaya tahap dan kumulatif ditampilkan di setiap gate, jadi pembengkakan terlihat
sebelum selesai — bukan sesudah.

Kalau perlu menekan biaya, turunkan `MODEL_FAKTA` lebih dulu: Fact-Checker
banyak membuka halaman web sehingga token masukannya paling besar. Jangan
menurunkan `MODEL_KURIKULUM`/`MODEL_BLUEPRINT`, karena hasilnya dipakai seluruh
pertemuan.

## Perencanaan (OpenSpec)

Proyek ini dibangun dengan [OpenSpec](https://github.com/Fission-AI/OpenSpec)
1.13.1 — spesifikasi disepakati sebelum kode ditulis.

```
openspec/
├── specs/                          spesifikasi yang berlaku
└── changes/
    ├── bangun-pipeline-materi/     pipeline awal
    ├── perkuat-agen-materi/        hook, pemeriksa, contoh di prompt
    └── alur-per-point/             alur per point, Fact-Checker, paket pertemuan
        ├── proposal.md    kenapa dan apa yang berubah
        ├── specs/         produksi-per-point, paket-pertemuan, verifikasi-fakta
        ├── design.md      keputusan teknis D1–D9 beserta alasannya
        └── tasks.md       rincian pekerjaan implementasi
```

```bash
npm i -g @fission-ai/openspec@latest    # butuh Node.js >= 20.19.0
openspec status --change alur-per-point
openspec validate alur-per-point --strict
```

Slash command di Claude Code: `/opsx:explore`, `/opsx:propose`, `/opsx:apply`,
`/opsx:archive`.

## Dokumentasi lain

- [MANUAL.md](MANUAL.md) — cara mengubah perilaku peran, arti tiap variabel
  `.env`, cara memproduksi ulang satu point atau satu pertemuan.
