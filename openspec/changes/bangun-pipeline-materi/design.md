# Design

## Context

Lihat `proposal.md` — Why untuk motivasinya.

Proyek `ai-office` yang sudah berjalan menyediakan pola yang terbukti: tiap
tahap adalah satu pemanggilan `query()` Claude Agent SDK dengan system prompt
per peran yang dimuat dari berkas Markdown, gate persetujuan berbasis terminal
yang juga dapat dijawab dari Telegram dan dashboard, event log JSONL, dan kunci
satu-pipeline. Batasan yang mengikat desain ini:

- Agent berjalan di atas Claude Code, jadi penyedia model harus melayani skema
  Anthropic (`/v1/messages`).
- Peran AI tidak bisa menulis berkas biner. DOCX dan PPTX harus dihasilkan
  proses Python dari sumber Markdown.
- Volume kerja sebanding dengan jumlah pertemuan: silabus 20 sesi berarti 20×
  pekerjaan produksi. Ini menentukan di mana paralelisme dan gate ditaruh.
- Seluruh peran dijalankan di model opus atas permintaan pemilik proyek, jadi
  penghematan tidak bisa datang dari pemilihan model — hanya dari tidak
  mengulang pekerjaan yang sudah benar.

## Goals / Non-Goals

**Goals:**

- Satu perintah dari silabus ke materi lengkap, dengan empat titik persetujuan
  manusia.
- Tiap luaran materi dapat dilacak ke satu butir blueprint, dan tiap butir
  blueprint ke satu capaian pembelajaran.
- Produksi ulang satu pertemuan tidak menyentuh pertemuan lain.
- Berkas biner selalu turunan dari sumber Markdown, tidak pernah sebaliknya.

**Non-Goals:**

- Bukan LMS: tidak ada pengelolaan peserta, nilai, atau pengumpulan tugas.
- Tidak menulis silabus dari nol; silabus adalah masukan, bukan luaran.
- Tidak menerjemahkan materi ke bahasa lain; hanya Indonesia dengan glosarium
  Inggris.
- Tidak ada rendering PDF; DOCX dan PPTX sudah cukup untuk distribusi.
- Tidak melakukan OCR pada PDF hasil pindai — ditolak di intake dengan pesan
  jelas.

## Decisions

### D1. Pilot satu pertemuan sebagai gate ketiga

Gaya, kedalaman, dan format materi adalah hal yang paling sulit dijelaskan lewat
prompt dan paling mahal kalau salah. Memproduksi satu pertemuan penuh lalu
meminta persetujuan menukar biaya satu pertemuan untuk menghindari risiko salah
gaya di seluruh silabus.

Masukan pengguna atas pilot tidak hanya dipakai merevisi pilot itu — masukan itu
disimpan sebagai `docs/ACUAN_GAYA.md` dan disuntikkan ke prompt Writer, Slide,
dan Lab Engineer untuk semua pertemuan berikutnya. Tanpa itu, koreksi gaya akan
hilang begitu pilot lewat.

*Alternatif yang dipertimbangkan:* menaruh contoh gaya di prompt sejak awal.
Ditolak karena pemilik proyek belum tentu tahu gaya yang diinginkannya sebelum
melihat satu pertemuan jadi.

### D2. Blueprint sebagai kontrak produksi, bukan saran

Produksi berjalan paralel per pertemuan, jadi tidak ada satu peran yang melihat
keseluruhan materi saat menulisnya. Yang menjaga koherensi adalah blueprint:
peran produksi hanya boleh memproduksi luaran yang tercantum di sana, dan
alokasi waktu segmennya harus berjumlah tepat sama dengan durasi sesi. Blueprint
menjadi satu-satunya tempat koherensi lintas pertemuan diputuskan, dan
satu-satunya dokumen yang perlu ditelaah manusia untuk memeriksanya.

### D3. Tiga peran produksi terpisah, bukan satu

Modul prosa, deck presentasi, dan lab kode adalah tiga kerajinan berbeda dengan
kriteria mutu yang bertentangan: modul ingin lengkap, slide ingin padat, lab
ingin jalan. Satu peran yang mengerjakan ketiganya cenderung mengoptimalkan satu
dan mengorbankan dua lainnya — dalam praktik, menghasilkan slide berupa paragraf
modul.

Pemisahan ini juga memberi Lab Engineer alasan untuk punya tool `Bash` tanpa
memberikannya ke peran yang menulis prosa.

*Alternatif yang dipertimbangkan:* satu peran Writer untuk semua luaran. Ditolak
karena alasan mutu di atas; bukan karena biaya, sebab ketiganya jalan paralel.

### D4. Lab wajib dieksekusi, bukan hanya ditulis

Kunci jawaban lab yang salah lebih merusak daripada tidak ada lab: pengajar
memakainya di depan kelas. Karena itu solusi lab harus benar-benar dijalankan
Lab Engineer sampai keluar tanpa galat, dan keluarannya dicatat di langkah
praktikum sebagai hasil yang diharapkan. Gagal setelah batas percobaan adalah
kegagalan tahap, bukan peringatan.

### D5. Luaran biner dihasilkan skrip, sumbernya Markdown

Peran AI menulis Markdown; `exporter.py` mengubahnya menjadi DOCX (`python-docx`)
dan PPTX (`python-pptx`). Konsekuensi yang disengaja: revisi apa pun mengubah
Markdown lalu menghasilkan ulang biner, sehingga DOCX/PPTX tidak pernah
menyimpang dari sumbernya dan hasil revisi tidak perlu ditelusuri di dua tempat.

Format PPTX memakai satu template sederhana dengan tata letak judul-dan-isi;
batas kepadatan slide (jumlah butir dan panjang butir) ditetapkan di
`prompts/_standar.md` sehingga bisa diubah tanpa menyentuh kode.

### D6. Glosarium sebagai berkas bersama, bukan hasil telaah akhir

Produksi paralel berarti dua pertemuan bisa memilih istilah Indonesia berbeda
untuk konsep yang sama. Glosarium `docs/GLOSARIUM.md` dibuat peran Kurikulum
sejak awal dari istilah yang muncul di silabus, dibaca semua peran produksi, dan
ditambah Editor saat telaah. Menyerahkan penyeragaman sepenuhnya ke Editor di
akhir berarti menulis ulang materi yang sudah jadi.

### D7. Level peserta disimpulkan, dan asumsinya dilaporkan

Karena level tidak dipatok di kode, ada risiko peran Kurikulum menebak diam-diam
dan seluruh materi mengikuti tebakan yang salah. Mitigasinya: bila silabus tidak
memberi petunjuk, asumsi level yang dipakai wajib ditulis eksplisit di dokumen
kurikulum dan ditampilkan di gate pertama — tempat termurah untuk mengoreksinya.

### D8. Infrastruktur operasional diadopsi, bukan dibagi

`monitor.py`, `dashboard.py`, dan `control.py` disalin dan disesuaikan ke
`ai-academy`, bukan diimpor dari `ai-office`. Dua proyek ini punya daftar tahap
dan bentuk luaran yang berbeda, dan keduanya masih berubah. Menjadikannya paket
bersama sekarang berarti setiap perubahan di satu proyek menanggung risiko
merusak yang lain, dengan imbalan yang belum jelas.

*Trade-off yang diterima:* perbaikan bug infrastruktur harus dikerjakan dua kali.

## Risks / Trade-offs

- **Biaya membengkak di silabus panjang** (semua peran opus, 20+ pertemuan × 3
  peran produksi) → plafon biaya per tahap dan per pertemuan di `.env`; biaya
  tahap dan kumulatif ditampilkan di tiap gate sehingga pembengkakan terlihat
  sebelum selesai, bukan sesudah.
- **Gate pilot menambah satu putaran tunggu manusia** → pertemuan pilot
  diproduksi dengan ketiga peran paralel, jadi menunggu satu pertemuan, bukan
  tiga tahap berurutan.
- **Lab Engineer punya akses `Bash`** → daftar perintah terlarang berlaku untuk
  semua peran; eksekusi dibatasi ke dalam direktori proyek; penolakan perintah
  dicatat sebagai event.
- **Ekstraksi PDF berantakan** (tabel jadi teks acak, kolom tertukar) → teks
  hasil normalisasi disimpan sebagai berkas di ruang kerja dan ditampilkan di
  gate pertama, sehingga silabus yang terbaca salah tertangkap sebelum produksi.
- **Produksi paralel menyentuh berkas yang sama** (glosarium) → peran produksi
  hanya membaca glosarium; penambahan istilah dikumpulkan per pertemuan dan
  digabungkan Editor, sehingga tidak ada dua proses menulis satu berkas.
- **Dashboard dapat menjalankan pipeline berakses `Bash`** → terikat
  `127.0.0.1` secara bawaan, dan menolak berjalan bila dibuka ke jaringan tanpa
  sandi.

## Migration Plan

Proyek baru, tidak ada data lama yang perlu dimigrasikan. Urutan penyebaran:

1. `pip install -r requirements.txt` di venv proyek.
2. Salin `.env.example` ke `.env`; biarkan `ANTHROPIC_API_KEY` kosong untuk
   memakai langganan Claude.
3. Jalankan satu silabus pendek (2–3 pertemuan) sampai selesai sebagai uji asap
   sebelum memakai silabus penuh.

Rollback: hapus direktori proyek di `workspace/`. Tidak ada state di luar
direktori proyek selain berkas kunci di `.locks/`.

## Open Questions

- Template PPTX: apakah perlu mengikuti identitas visual lembaga (logo, warna,
  font) atau template netral sudah cukup? Dapat dijawab setelah deck pertama
  terlihat; tidak mengubah spec maupun pembagian tugas, hanya isi
  `exporter.py`.
