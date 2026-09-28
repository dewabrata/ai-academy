# Manual AI Academy

Panduan operasional. Untuk gambaran umum dan cara jalan pertama kali, lihat
[README.md](README.md).

---

## 1. Mengubah perilaku peran

**Semua perilaku peran ada di `prompts/`, bukan di kode.** Ubah berkas
Markdown-nya, jalankan ulang tahap yang bersangkutan — tidak ada yang perlu
di-restart selain pipeline itu sendiri.

| Berkas | Mengatur |
|---|---|
| `prompts/_standar.md` | Aturan yang berlaku ke **semua** peran: bahasa, gaya penulisan pemilik proyek, kejujuran isi, penanda `[CEK-FAKTA]`, format blok KESENJANGAN |
| `prompts/kurikulum.md` | Struktur `KURIKULUM.md`, cara menyimpulkan level peserta, jenis tugas per pertemuan |
| `prompts/blueprint.md` | Struktur `BLUEPRINT.md`, **format `### Point` dan `### Tugas`**, konvensi lintas pertemuan |
| `prompts/writer.md` | Struktur dan kedalaman satu point, penanda klaim produk, cara merevisi dari catatan |
| `prompts/reviewer.md` | Gaya catatan revisi, 7 lensa mutu, rubrik skor tersembunyi, mode point dan mode paket |
| `prompts/fakta.md` | Apa yang diverifikasi Fact-Checker dan format laporannya |
| `prompts/slide.md` | **Format wajib `SLIDE.md`**, susunan deck, batas kepadatan, catatan trainer |
| `prompts/tugas.md` | `LATIHAN.md`/`KUNCI.md`/`PRAKTIK.md`/`lab/`, format AIKEN, kewajiban eksekusi solusi |
| `prompts/editor.md` | Batas wewenang penyuntingan, penggabungan glosarium |

### Contoh: point terlalu panjang atau terlalu pendek

Ubah `POINT_HALAMAN` di `.env` (bawaan `10–20`). Nilainya masuk langsung ke
prompt Writer. Untuk mengubah *cara* mencapai kedalaman itu, edit bagian
`## Kedalaman: level handbook` di `prompts/writer.md`.

### Contoh: slide masih terlalu padat

Batas kepadatan ada di **dua** tempat dan harus diubah bersamaan:

1. `prompts/slide.md` — supaya peran Slide tahu targetnya.
2. `exporter.py`, konstanta `MAKS_BUTIR`, `MAKS_KATA_BUTIR`, `MAKS_BARIS_KODE` —
   supaya pelanggarannya terdeteksi.

Pelanggaran kepadatan dikembalikan ke peran Slide saat itu juga lewat hook, dan
tetap dicatat pemeriksa. Konversi PPTX tidak digagalkan.

### Contoh: mengubah format `SLIDE.md` atau `### Point`

Keduanya kontrak antara prompt dan kode:

- `SLIDE.md` ↔ `parse_slides()` di `exporter.py`.
- `### Point` / `### Tugas` ↔ `rencana.py`.

Kalau salah satu diubah tanpa yang lain, deck akan kosong atau daftar point
tidak terbaca. Periksa tanpa memanggil model:

```bash
python exporter.py workspace/<proyek>
python -c "import rencana,pathlib; print(rencana.daftar_pertemuan(pathlib.Path('workspace/<proyek>')))"
```

---

## 2. Variabel `.env`

### Autentikasi

| Variabel | Arti |
|---|---|
| `ANTHROPIC_API_KEY` | Kosongkan untuk memakai **langganan** Claude (harus sudah `claude` → `/login`). Isi untuk pay-as-you-go |
| `CLAUDE_CLI_PATH` | Path ke `claude.exe`. Isi kalau SDK tidak menemukannya sendiri; SDK menolak shim `.cmd` di Windows |
| `AI_PROVIDER` | `claude` \| `openrouter` \| `custom` |
| `CUSTOM_BASE_URL`, `CUSTOM_API_KEY`, `CUSTOM_MODEL` | Host pihak ketiga. **Wajib melayani skema Anthropic** (`/v1/messages`) |
| `CUSTOM_MODEL_OPUS/SONNET/HAIKU` | Petakan alias per tingkat ke nama model di host itu |
| `USE_OPENROUTER`, `OPENROUTER_API_KEY` | Jalur cadangan OpenRouter |

Kalau modelnya bukan Claude, perhitungan biaya tidak dapat dipercaya, jadi
plafon `BUDGET_*` bisa tidak pernah terpicu. Seluruh silabus dan materi juga
dikirim ke host tersebut.

### Model per peran

`MODEL_KURIKULUM`, `MODEL_BLUEPRINT`, `MODEL_WRITER`, `MODEL_REVIEWER`,
`MODEL_FAKTA`, `MODEL_SLIDE`, `MODEL_TUGAS`, `MODEL_EDITOR`.

Nilai: `haiku` | `sonnet` | `opus`, atau id model lengkap (mis.
`claude-opus-5`) kalau ingin terkunci — alias `opus`/`sonnet` tidak terikat
tanggal dan bisa berpindah sendiri saat Claude Code diperbarui. Model yang
**benar-benar** dipakai dicatat tiap tahap di `events.jsonl` sebagai event
`model`.

Bawaan semuanya `opus`.

### Produksi per point

| Variabel | Arti |
|---|---|
| `POINT_HALAMAN` | Panjang target satu point, masuk ke prompt Writer. Bawaan `10–20` |
| `POINT_MAKS_PUTARAN` | Batas putaran loop telaah per point. Bawaan `3`. Lewat batas ini point dieskalasi ke gate pertemuan |
| `LAB_MAX_PERCOBAAN` | Batas percobaan peran Tugas memperbaiki solusi lab yang gagal dieksekusi |

### Biaya

| Variabel | Untuk |
|---|---|
| `BUDGET_KURIKULUM`, `BUDGET_BLUEPRINT` | tahap perencanaan |
| `BUDGET_POINT_WRITER` | per point, per putaran (bawaan 4.0) |
| `BUDGET_POINT_REVIEW` | Reviewer per point, per putaran (bawaan 1.5) |
| `BUDGET_POINT_FAKTA` | Fact-Checker per point, per putaran (bawaan 1.5) |
| `BUDGET_SLIDE`, `BUDGET_TUGAS` | paket per pertemuan (bawaan 3.0 dan 4.0) |
| `BUDGET_PAKET_REVIEW` | telaah paket per pertemuan (bawaan 2.0) |
| `BUDGET_EDITOR` | tahap akhir (bawaan 4.0) |
| `BUDGET_PROYEK` | plafon total; kalau terlampaui pipeline **bertanya**, tidak memutus. `0` atau kosong = tanpa plafon |

Perkiraan kasar satu pertemuan 10 point: 10 × (Writer + Reviewer + Fakta) ×
±1,5 putaran, ditambah paket. Naikkan `BUDGET_PROYEK` sebelum produksi nyata
dengan Opus, atau pipeline akan berhenti bertanya di tengah jalan.

### Kuota langganan

| Variabel | Arti |
|---|---|
| `QUOTA_WAIT` | `auto` = tidur sampai waktu reset dari server lalu ulang tahap. `ask` = selalu tanya dulu |
| `QUOTA_WAIT_MAX_HOURS` | Kalau tunggunya lebih lama dari ini (mis. kuota mingguan), tetap tanya dulu walau `auto` |

### Monitoring & dashboard

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DASHBOARD_HOST`, `DASHBOARD_PORT`,
`DASHBOARD_USER`, `DASHBOARD_PASS`.

`DASHBOARD_PASS` **wajib** kalau `DASHBOARD_HOST` bukan alamat lokal; tanpa itu
dashboard menolak jalan. Selama kosong, dashboard dipakai tanpa login.

Semua setelan di atas juga bisa diubah dari halaman **Pengaturan** di dashboard.
Nilai rahasia (token Telegram, API key, kata sandi) tidak pernah dikirim ke
browser: yang tampil hanya status terisi atau kosong, dan kolom yang dikosongkan
mempertahankan nilai lama.

---

## 3. Opsi per proyek

Opsi luaran disimpan di `workspace/<proyek>/docs/OPSI.json`, dengan bawaan dari
`.env`:

| Opsi | Arti |
|---|---|
| `slide` | Salah = peran Slide **tidak dijalankan** untuk proyek itu. Hemat biaya model, dan pemeriksaan slide menjadi "tidak berlaku" |
| `ekspor_docx`, `ekspor_pptx` | Salah = konversi biner dilewati. Sumber Markdown tetap dibuat dan bisa dikonversi belakangan dengan `python exporter.py workspace/<proyek>` |
| `point_halaman`, `point_maks_putaran` | Sama seperti `.env`, tetapi per proyek |
| `model` | Kosong = ikut `MODEL_<PERAN>` di `.env`. Diisi = seluruh peran memakai model itu |

Paling mudah diisi dari layar **Proyek baru** di dashboard. Untuk proyek yang
sudah ada, sunting berkasnya langsung, lalu jalankan tahap berikutnya.

Proyek lama tanpa `OPSI.json` memakai bawaan `.env`, jadi perilakunya tidak
berubah.

## 4. Mengelola proyek (arsip, ganti nama, duplikat)

Dari tab **Proyek** di dashboard, atau langsung di disk:

| Aksi | Yang terjadi | Syarat |
|---|---|---|
| Arsipkan | `workspace/<nama>` dipindahkan ke `workspace/.arsip/<nama>-<waktu>` | pipeline proyek itu tidak berjalan |
| Pulihkan | Arsip dikembalikan ke `workspace/<nama baru>` | nama tujuan belum dipakai |
| Hapus permanen | Folder arsip dihapus, tidak bisa dibatalkan | nama arsip diketik persis |
| Ganti nama | Folder proyek dipindah, kunci lama dibuang | pipeline tidak berjalan, nama baru belum dipakai |
| Duplikat setelan | Proyek baru berisi silabus, `KLIEN.md`, dan `OPSI.json` yang sama — **tanpa materi** | nama baru belum dipakai |

Tidak ada tombol "hapus proyek" langsung. Satu proyek bisa bernilai puluhan
dolar biaya produksi, jadi penghapusan sengaja dibuat dua langkah.

### Slide dibuat menyusul

Proyek yang dibuat dengan slide dimatikan tetap bisa mendapat slide belakangan.
Point tidak disentuh, karena slide memang dibangun dari point final:

```bash
python academy.py --project <nama> --slide semua   # semua pertemuan yang belum punya
python academy.py --project <nama> --slide 3       # satu pertemuan
```

Di dashboard: tab **Materi** → tombol **Buat slide** pada baris pertemuan, atau
**Buat slide untuk semua pertemuan**. Pertemuan yang sudah punya `SLIDE.md`
dilewati tanpa memanggil model, dan `OPSI.json` diperbarui supaya produksi
berikutnya ikut membuat slide.

### Mengunduh materi

Tab **Materi** menyediakan tiga bentuk unduhan:

| Tombol | Isi |
|---|---|
| Unduh semua materi (.zip) | seluruh `materi/` + KURIKULUM, BLUEPRINT, GLOSARIUM, PEMERIKSAAN — tanpa catatan proses |
| .zip termasuk catatan telaah | ditambah `review/` dan `*.catatan.md` |
| .zip pada baris pertemuan | hanya pertemuan itu |

## 5. Konteks klien

```bash
python academy.py silabus.docx --klien konteks/klien-dika.md
```

Berkas itu disalin ke `docs/KLIEN.md` dan dibaca semua peran. Isinya: industri,
audiens, sensitivitas data, tool yang dipakai, dan aturan gaya khusus klien.
Aturan di sana **menang** atas aturan umum di `prompts/_standar.md`.

Pakai ini untuk hal yang berbeda antarklien. Aturan yang berlaku untuk semua
proyek Anda tempatnya di `prompts/_standar.md`, bagian
`## Gaya penulisan pemilik proyek`.

---

## 6. Melanjutkan proyek

```bash
python academy.py --project <nama> --resume <tahap>
```

Tahap: `kurikulum` → `blueprint` → `produksi` → `akhir`. Proyek lama yang
`STATE.txt`-nya masih berisi `pilot` atau `telaah` otomatis dipetakan ke
`produksi`.

Tanpa `--resume`, pipeline melanjutkan dari `docs/STATE.txt`. Proyek yang sudah
`selesai` dijalankan lagi akan masuk ke `akhir`, bukan memproduksi dari nol.

Yang dilewati saat melanjutkan:

- Tahap yang `docs/<NAMA>.md`-nya sudah ada **dan** masih menunggu gate: langsung
  ke gate, dokumen tidak digenerate ulang.
- Point yang statusnya `siap` atau `eskalasi` di `docs/PRODUKSI.json`.
- Putaran yang sudah selesai: kalau Writer sudah menulis tetapi telaahnya
  terputus, yang diulang hanya telaahnya.
- Pertemuan yang gate-nya sudah disetujui (ditandai `.GATE_OK` di foldernya).

Kalau satu tahap terputus di tengah, `docs/SESSIONS.json` menyimpan `session_id`
Claude Code-nya dan tahap itu dilanjutkan dari titik terakhir.

---

## 7. Menjawab gate

Tiga kanal, yang tiba lebih dulu yang dipakai:

1. **Terminal** — ketik langsung.
2. **Dashboard** — tombol Setuju/Berhenti atau kotak masukan. Ditulis ke
   `docs/GATE_JAWAB.txt` dan dibaca `monitor.ask`.
3. **Telegram** — tiga tombol yang sama dengan dashboard: **Setuju, lanjutkan**,
   **Berhenti**, dan **Tulis masukan**. Tombol ketiga membuka kolom isian
   (ForceReply) dengan contoh di dalamnya; masukan juga bisa dikirim langsung
   dengan membalas pesan gate.

| Jawaban | Akibat |
|---|---|
| `y` | lanjut |
| `q` | pipeline berhenti; **semua dokumen tetap tersimpan** |
| teks lain | materi direvisi sesuai masukan, lalu gate yang sama ditanyakan lagi |

Apa yang dilakukan masukan teks, per gate:

| Gate | Masukan teks |
|---|---|
| `KURIKULUM`, `BLUEPRINT` | disimpan sebagai `docs/<NAMA>_FEEDBACK.md`, dokumen ditulis ulang |
| `PILOT` | ditambahkan ke `docs/ACUAN_GAYA.md` — **berlaku untuk semua point berikutnya** — lalu point pilot direvisi |
| `PERTEMUAN-n` | ditambahkan ke `materi/pertemuan-NN/MASUKAN.md`. Writer menentukan point mana yang terkena dan merevisinya, point itu ditelaah ulang, lalu paket dibangun ulang |

Di gate pertemuan, masukan Anda juga berfungsi sebagai **jawaban atas
pertanyaan** di `PERTANYAAN.md`.

---

## 8. Memproduksi ulang satu point atau satu pertemuan

Status point ada di `docs/PRODUKSI.json`, dengan kunci `<pertemuan>.<point>`,
misalnya `01.03`.

```bash
# Satu point: hapus entri statusnya dan berkas point-nya
python - <<'EOF'
import json, pathlib
p = pathlib.Path("workspace/<proyek>/docs/PRODUKSI.json")
d = json.loads(p.read_text(encoding="utf-8")); d.pop("01.03", None)
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
EOF
rm workspace/<proyek>/materi/pertemuan-01/point/point-03.md
rm workspace/<proyek>/materi/pertemuan-01/.PAKET_OK workspace/<proyek>/materi/pertemuan-01/.GATE_OK
python academy.py --project <proyek> --resume produksi
```

```bash
# Satu pertemuan penuh
rm -r workspace/<proyek>/materi/pertemuan-NN
python academy.py --project <proyek> --resume produksi
```

Kalau yang ingin diulang hanya **paketnya** (slide, tugas, quiz) tanpa menulis
ulang point, hapus `.PAKET_OK` dan `.GATE_OK` saja.

Untuk hanya menghasilkan ulang handbook dan berkas biner tanpa memanggil model —
misalnya setelah Anda menyunting sebuah point sendiri:

```bash
python exporter.py workspace/<proyek>
```

Perhatikan: `exporter.py` menghasilkan biner dari sumber Markdown, sedangkan
`HANDBOOK.md` digabung ulang saat pipeline berjalan. Kalau Anda menyunting point
di luar pipeline, jalankan juga:

```bash
python -c "import exporter,pathlib; exporter.gabung_handbook(pathlib.Path('workspace/<proyek>/materi/pertemuan-01'), 'Pertemuan 1 — Judul')"
```

---

## 9. Pemulihan saat pipeline berhenti

**Langkah pertama selalu sama — tanya keadaannya, jangan menebak:**

```bash
./academyctl.sh status          # dashboard + semua proyek sekaligus
.\academyctl.ps1 status         # Windows

python control.py status                       # semua proyek
python control.py status <proyek>              # + saran langkah berikutnya
```

Bedakan dua hal yang sering tertukar:

- **Dashboard mati** — panelnya tidak bisa dibuka, tetapi pipeline yang sudah
  jalan tetap bekerja, karena ia proses terpisah dengan sesi sendiri.
  Pemulihannya `./academyctl.sh start` (atau `systemctl start ai-academy`).
- **Pipeline berhenti** — materi tidak bertambah. Itu yang dibahas tabel di
  bawah, dan dashboard tidak ada hubungannya.

Menghentikan dashboard tidak pernah menghentikan pipeline. Itu disengaja: satu
pertemuan bisa berjam-jam dan puluhan dolar.

Perintah itu menyebut satu dari empat keadaan, dan langsung memberi perintah
yang perlu dijalankan.

| Keadaan | Artinya | Pemulihan |
|---|---|---|
| `berjalan` | Pipeline hidup dan bekerja | Tidak perlu apa-apa |
| `MENUNGGU GATE` | Pipeline sehat, tetapi menunggu keputusan Anda | Jawab di dashboard/Telegram, atau `python control.py jawab <proyek> y` |
| `kunci basi` | Proses mati (PC restart, listrik, ditutup) | `python control.py lanjut <proyek>` |
| `berhenti` | Proses sudah tidak ada | `python control.py lanjut <proyek>` |

**Yang tidak hilang saat proses mati:** semua berkas point, catatan Reviewer dan
Fact-Checker, status tiap point di `docs/PRODUKSI.json`, dan `docs/SESSIONS.json`
yang menyimpan sesi tiap tahap. Melanjutkan berarti benar-benar melanjutkan:
point yang sudah siap tidak ditulis ulang, dan tahap yang terputus disambung
dari sesi terakhirnya.

### Gejala yang sering disalahartikan

- **"Pipeline tidak jalan padahal tombol sudah ditekan."** Biasanya gate basi:
  gate dari proses yang sudah mati. Dashboard sekarang menyembunyikannya, dan
  `control.py status` tidak akan menyebut `MENUNGGU GATE` untuk gate seperti itu.
- **"Dashboard mati berarti produksi berhenti."** Tidak. Pipeline berjalan
  sebagai proses terpisah. Dashboard hanya memantau dan mengendalikan, jadi bisa
  dimatikan dan dijalankan lagi kapan saja.
- **"Tidak ada log baru selama berjam-jam."** Cek kuota di `status.json`. Kalau
  kuota habis dan `QUOTA_WAIT=auto`, pipeline memang sedang tidur menunggu reset,
  lalu melanjutkan sendiri.

### Kalau kunci benar-benar tersangkut

```bash
python control.py kunci <proyek>     # dihapus HANYA kalau PID-nya sudah mati
```

Kunci yang dipegang proses hidup tidak akan dihapus; Anda diminta menghentikan
pipeline-nya lebih dulu. Ini mencegah dua pipeline menulis ke proyek yang sama.

### Pemulihan berat: mengulang satu bagian

Kalau hasilnya rusak (bukan prosesnya), lihat §8 untuk memproduksi ulang satu
point atau satu pertemuan. Untuk kembali ke keadaan sebelum percobaan, arsipkan
proyeknya (§4) — arsip bisa dipulihkan, jadi tidak ada yang terbuang.

## 10. Kalau ada yang salah

### Silabus PDF terbaca berantakan

Gate KURIKULUM menampilkan cuplikan teks yang **benar-benar dibaca peran**, dari
`sumber/silabus.txt`. Kalau yang tampil acak-acakan, silabusnya PDF hasil pindai
atau tabelnya tidak terbaca. Jawab `q`, konversi silabus ke `.md`/`.docx`, lalu
jalankan ulang.

### Daftar point di gate Blueprint salah

Gate BLUEPRINT menampilkan point yang dibaca Python, satu per satu. Tanda
`!! tanpa capaian` atau jumlah point yang tidak sesuai silabus berarti blueprint
perlu diperbaiki. Jawab dengan masukan teks (mis. "point pertemuan 2 harus 6
sesuai silabus, jangan digabung"), atau perbaiki `docs/BLUEPRINT.md` manual lalu
`--resume blueprint`.

Format yang dibaca:

```
### Point
1. Judul point — P1-1, P1-2
   - arah isi ditulis menjorok, sebagai butir
### Tugas
Jenis: praktik | lab-kode | praktik+lab-kode
```

Daftar bernomor **kedua** di bawah daftar point tidak dibaca sebagai point.

### Satu point tidak pernah siap (selalu dieskalasi)

Baca catatan terakhirnya di `materi/pertemuan-NN/review/`. Penyebab yang paling
sering: Reviewer dan Fact-Checker meminta hal yang bertentangan. Aturannya,
Fact-Checker menang untuk urusan fakta produk. Kalau pertentangan lain muncul,
jawab di gate pertemuan — masukan Anda menang atas keduanya.

### Quiz AIKEN ditolak Moodle

`docs/PEMERIKSAAN.md` memeriksanya lebih dulu: tepat 10 soal, teks soal satu
baris, pilihan `A. ` berurutan, dan `ANSWER:` yang menunjuk pilihan yang ada.
Kalau pemeriksaan itu lulus tetapi Moodle tetap menolak, periksa encoding berkas
(harus UTF-8) dan baris kosong antarsoal.

### Lab gagal dieksekusi terus

Peran Tugas melaporkan tahap gagal alih-alih menyerahkan lab yang tidak jalan.
Periksa `lab/solusi/` dan `pipeline.log`. Biasanya karena blueprint menuntut
dependensi yang tidak ada di mesin ini.

### "Pipeline lain sedang berjalan"

Satu pipeline per proyek. Kalau proses sebelumnya mati mendadak, kuncinya di
`.locks/<proyek>.lock` tertinggal — pipeline berikutnya memeriksa apakah PID-nya
masih hidup dan mengambil kunci yang kedaluwarsa secara otomatis. Kalau masih
tersangkut, hapus berkas kunci itu.

### Kuota langganan habis di tengah produksi

Dengan `QUOTA_WAIT=auto`, pipeline tidur sampai waktu reset dari server lalu
mengulang tahap yang sama — tidak ada pekerjaan yang hilang, karena status point
sudah tersimpan. Kalau resetnya lebih dari `QUOTA_WAIT_MAX_HOURS`, Anda ditanya
dulu.

---

## 11. Membaca jejak

| Berkas | Isi |
|---|---|
| `docs/PRODUKSI.json` | Status tiap point: `siap`/`eskalasi`/`proses`, putaran, riwayat skor tersembunyi Reviewer |
| `materi/pertemuan-NN/PROSES.md` | Ringkasan proses per point: putaran, butir revisi tiap putaran, status fakta, skor terakhir |
| `materi/pertemuan-NN/PERTANYAAN.md` | Pertanyaan Reviewer dan Writer yang terkumpul |
| `docs/PEMERIKSAAN.md` | Skor pemeriksaan deterministik per pertemuan |
| `docs/events.jsonl` | Satu event per baris: `stage_start`, `stage_end`, `point`, `gate`, `gate_answer`, `model`, `tool`, `tool_denied`, `export`, `pemeriksaan`, `quota`, `error` |
| `docs/status.json` | Snapshot: tahap sekarang, point yang dikerjakan, gate yang menunggu, biaya per tahap dan total |
| `docs/pipeline.log` | Keluaran mentah pipeline |
| `docs/SESSIONS.json` | `session_id` per tahap, untuk melanjutkan tahap yang terputus |
| `docs/STATE.txt` | Tahap terakhir yang tercatat |

Semuanya bisa dibuka dari dashboard, dan biayanya ditampilkan per tahap.

---

## 12. Mengubah spesifikasi

Perubahan perilaku yang nyata sebaiknya lewat OpenSpec, bukan langsung ke kode:

```bash
openspec status --change alur-per-point
/opsx:propose "tambah luaran naskah video per point"
```

Spesifikasi yang berlaku ada di `openspec/specs/`; usulan perubahan di
`openspec/changes/`. Keputusan teknis beserta alasannya — termasuk mengapa
daftar point dibaca dari blueprint dan bukan dari silabus, dan mengapa handbook
digabung Python — ada di `openspec/changes/alur-per-point/design.md`.
