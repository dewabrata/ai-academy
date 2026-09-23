# Proposal

## Why

Prompt ketujuh peran sudah mendefinisikan *bentuk* luaran, tetapi hampir tidak
memberi contoh, tidak menuntun *urutan berpikir*, dan tidak punya kriteria
lulus yang eksplisit. Aturan-aturan penting ("jangan tulis di luar folder
pertemuanmu", "jangan buat .docx", batas kepadatan slide) hanya diminta lewat
prompt dan baru ketahuan dilanggar di telaah akhir, setelah seluruh pertemuan
diproduksi — tempat termahal untuk memperbaikinya.

Pola dari koleksi `everything-claude-code` (contoh ❌/✓ berpasangan, proses
kerja bernomor, checklist berambang dengan vonis, hook yang menegakkan aturan
seketika, dan eval harness) menjawab ketiga kekurangan itu. Perubahan ini
mengadopsinya untuk domain materi ajar, dan mengukur hasilnya terhadap baseline
supaya "lebih pintar" dibuktikan, bukan diasumsikan.

## What Changes

- **Prompt peran diperkuat**: tiap peran mendapat bagian *Proses kerja*
  bernomor, *Contoh* ❌/✓ berpasangan untuk keputusan tersulit perannya, dan
  *Cek mandiri* sebelum selesai. Contoh awal ditulis dari nol; akan diganti
  contoh dari materi asli pemilik proyek begitu tersedia.
- **Reviewer diberi rubrik berskor dan vonis** per pertemuan (LULUS /
  PERLU-REVISI / TOLAK) dengan ambang eksplisit.
- **Hook penegakan saat penulisan** di pipeline (hook Agent SDK, bukan
  `.claude/`): penulisan di luar folder milik peran ditolak, penulisan
  `.docx`/`.pptx` ditolak, dan pelanggaran kepadatan `SLIDE.md` dikembalikan ke
  peran Slide saat itu juga. Setiap penolakan dicatat sebagai event — menutup
  requirement `operasi-pipeline` yang belum terpenuhi.
- **Pemeriksa materi deterministik** (`pemeriksa.py`): skor per pertemuan dari
  pemeriksaan yang tidak butuh model — capaian tertutup, soal bertanda capaian,
  lembar latihan bebas jawaban, alokasi waktu blueprint, format slide, solusi
  lab jalan. Hasilnya ditampilkan di gate dan dipakai membandingkan run.
- **Uji asap berulang** (`uji/uji_asap.py`) dengan jawaban gate yang dipatok dan
  model yang dapat dipilih, untuk membandingkan versi prompt secara adil.

## Capabilities

### New Capabilities
- `evaluasi-materi`: pemeriksaan otomatis mutu materi yang deterministik,
  pelaporan skornya, dan uji asap yang dapat diulang untuk membandingkan versi.

### Modified Capabilities
- `produksi-materi`: penegakan aturan penulisan dan kepadatan slide saat itu
  juga, bukan di telaah akhir.
- `penjaminan-mutu-materi`: rubrik berskor dan vonis per pertemuan.
- `operasi-pipeline`: penolakan tool tercatat sebagai event.

## Impact

- Berkas berubah: `prompts/*.md`, `academy.py`, `roles.py`; baru: `pemeriksa.py`,
  `hooks_sdk.py`, `uji/uji_asap.py`.
- Tidak ada dependensi baru.
- Prompt menjadi lebih panjang, jadi token masukan per tahap naik. Diukur di uji
  asap; kalau kenaikan biaya tidak dibarengi kenaikan skor, contoh dipangkas.
- Uji dijalankan dengan Sonnet karena kuota langganan menipis; produksi tetap
  opus.
