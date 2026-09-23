# Design

## Context

Lihat `proposal.md` — Why. Pola diambil dari `WorldFlowAI/everything-claude-code`
(berkas `agents/*.md`, `skills/verification-loop`, `skills/eval-harness`,
`commands/orchestrate.md`, `hooks/hooks.json`), dibaca pada 22 Sep 2026.

Batasan yang mengikat:

- Pipeline memanggil Agent SDK dengan `setting_sources=[]`, jadi agent, skill,
  rule, dan hook dalam format `.claude/` **tidak dimuat**. Polanya harus
  dipindahkan ke `prompts/*.md` dan ke hook Python milik SDK.
- Kuota langganan menipis saat perubahan ini dikerjakan, jadi uji perbandingan
  memakai Sonnet. Produksi tetap opus.
- Contoh materi asli pemilik proyek belum tersedia; contoh ✓/❌ sementara ditulis
  dari nol.

## Goals / Non-Goals

**Goals:**

- Peran menerima contoh ✓/❌ untuk keputusan tersulitnya, proses kerja bernomor,
  dan cek mandiri yang bisa dijawab ya/tidak.
- Aturan yang bisa dicek mesin ditegakkan saat pelanggaran terjadi.
- Mutu materi punya angka yang bisa dibandingkan antarversi.

**Non-Goals:**

- Pustaka pelajaran lintas proyek (pola *continuous learning*). Ditunda: koreksi
  gaya satu proyek belum tentu berlaku untuk proyek lain, dan menyuntikkannya ke
  semua proyek berisiko menyebarkan selera satu kelas ke kelas lain. Dievaluasi
  lagi setelah ada koreksi dari beberapa proyek nyata.
- Mengubah jumlah peran, urutan tahap, atau letak gate.
- Grader berbasis model di luar Reviewer.

## Decisions

### D1. Isi pola dipindah ke prompts/, hook ke Python

Format `.claude/agents/*.md` tidak dimuat pipeline. Menyalinnya ke `.claude/`
hanya akan terlihat berfungsi di session interaktif dan diam-diam tidak
berpengaruh di pipeline. Bagian yang diambil — proses kerja, contoh, checklist —
ditambahkan ke `prompts/<peran>.md`; hook ditulis sebagai callback
`HookMatcher` di `hooks_sdk.py`.

### D2. Contoh ✓/❌ berpasangan, dengan alasan

Setiap contoh disertai satu kalimat *mengapa* ia salah atau benar. Contoh tanpa
alasan membuat model meniru permukaannya (nama tokoh, panjang kalimat); dengan
alasan, model meniru prinsipnya. Karena contoh memakai dunia "Rina /
pengeluaran", `_standar.md` melarang eksplisit memakai tokoh dan data dari
contoh kecuali sama dengan konvensi blueprint.

### D3. Tidak meniru gaya huruf kapital

Repo sumber memakai "MUST BE USED", "ALWAYS" tanpa alasan. Untuk model sekelas
opus, perintah beremfasis cenderung menghasilkan kepatuhan berlebihan di tempat
yang salah. Prompt ai-academy mempertahankan gaya menjelaskan *mengapa*.

### D4. Hook menolak dengan alasan yang bisa ditindaklanjuti

Penolakan tanpa alasan membuat peran mencoba jalan memutar. Setiap penolakan
menyebut apa yang diizinkan ("hanya boleh menulis di materi/pertemuan-01/";
"tulis ke ISTILAH.md"). Penolakan perintah terlarang juga diperiksa di hook,
walau `disallowed_tools` sudah mencegahnya, karena hanya hook yang bisa
mencatatnya sebagai event.

### D5. Umpan balik slide lewat PostToolUse, bukan penolakan

Slide yang terlalu padat tidak ditolak — isinya tetap tersimpan — tetapi
pelanggarannya dikembalikan lewat `additionalContext` supaya peran Slide
memperbaikinya dalam tahap yang sama. Menolak penulisan akan membuat peran
kehilangan draf utuhnya karena satu butir terlalu panjang.

### D6. Pemeriksa hanya mengukur aturan yang sudah ada di prompt lama

Setiap pemeriksaan di `pemeriksa.py` sesuai dengan aturan yang sudah tertulis di
prompt versi sebelum perubahan ini. Kalau pemeriksa mengukur konvensi baru yang
hanya dikenal prompt baru, versi baru akan menang karena aturannya, bukan karena
mutunya. Dengan begini, perbandingan baseline dan versi baru adil.

### D7. Wilayah tulis per tahap

| Tahap | Wilayah |
|---|---|
| KURIKULUM, BLUEPRINT, REVIEWER | `docs/` |
| WRITER/SLIDE/LAB-NN | `materi/pertemuan-NN/` |
| REVISI-* | `materi/` |
| EDITOR | seluruh ruang kerja (menggabung glosarium dan menyunting materi) |

## Risks / Trade-offs

- **Prompt lebih panjang → token masukan naik** → diukur di uji asap; kalau
  biaya naik tanpa kenaikan skor, contoh dipangkas.
- **Contoh satu domain bocor ke proyek lain** → larangan eksplisit di
  `_standar.md`, dan contoh diganti materi asli pemilik proyek begitu tersedia.
- **Silabus uji satu domain dengan contoh prompt** → sedikit menguntungkan versi
  baru pada vonis Reviewer. Pemeriksaan deterministik hampir tidak terpengaruh
  karena sifatnya mekanis. Dicatat di laporan perbandingan.
- **Pemeriksa menjalankan kode buatan model** → kode yang sama sudah dijalankan
  Lab Engineer; pemeriksa memakai batas waktu 60 detik dan berjalan di folder
  solusi.
- **Satu run per versi** → keluaran model bervariasi antarrun. Selisih kecil
  tidak bermakna; hanya selisih yang jelas yang dilaporkan sebagai perbaikan.

## Migration Plan

Tidak ada migrasi data. Proyek yang sedang berjalan memakai prompt baru pada
tahap berikutnya yang dijalankan.
