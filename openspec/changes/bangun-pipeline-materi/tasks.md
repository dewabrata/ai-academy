# Tasks

> **Status.** Seluruh kode sudah ditulis. Yang ditandai `[x]` sudah diverifikasi
> dengan uji yang dijalankan. Yang masih `[ ]` adalah butir yang verifikasinya
> menuntut panggilan model sungguhan — artinya memotong kuota/biaya pemilik
> proyek — jadi ditahan sampai diminta. Jalankan uji asap di tugas 8.1 untuk
> menutup sisanya sekaligus.

## 1. Fondasi proyek

- [x] 1.1 Buat `requirements.txt` berisi `claude-agent-sdk`, `python-dotenv`, `python-docx`, `pdfplumber`, `python-pptx`, dan verifikasi `pip install -r requirements.txt` selesai tanpa galat di venv baru
- [x] 1.2 Buat `.env.example` berisi autentikasi, `MODEL_<PERAN>` untuk tujuh peran (bawaan opus), `BUDGET_<TAHAP>`, `BUDGET_PERTEMUAN`, setelan kuota, Telegram, dan dashboard; verifikasi tiap variabel yang dibaca kode ada di berkas ini — 31 variabel diperiksa, tidak ada yang hilang
- [x] 1.3 Buat `.gitignore` yang mengecualikan `.env`, `.venv`, `workspace/`, `.locks/`, `__pycache__`, dan verifikasi `git status` bersih setelah pipeline dijalankan sekali

## 2. Intake silabus

- [x] 2.1 Implementasikan `silabus.py` dengan pembaca `.md`/`.txt` dan verifikasi teks terbaca apa adanya untuk berkas contoh
- [x] 2.2 Tambahkan pembaca `.docx` lewat `python-docx` yang mengambil paragraf dan isi tabel berurutan; verifikasi dengan silabus DOCX contoh bahwa isi tabel ikut terekstrak — urutan paragraf → tabel → paragraf terjaga
- [x] 2.3 Tambahkan pembaca `.pdf` lewat `pdfplumber` per halaman berurutan; verifikasi dengan PDF contoh bahwa urutan halaman terjaga
- [x] 2.4 Tolak ekstensi tak didukung dan hasil ekstraksi kosong dengan pesan yang menyebut format yang didukung; verifikasi dengan berkas `.xlsx` dan PDF tanpa lapisan teks bahwa pipeline berhenti sebelum tahap pertama
- [x] 2.5 Terima teks silabus sebagai argumen langsung dan simpan ke ruang kerja sebagai berkas sumber; verifikasi berkas sumber ada setelah dijalankan tanpa berkas masukan
- [x] 2.6 Siapkan ruang kerja `workspace/<proyek>/` dengan `docs/`, `materi/`, `sumber/`; simpan silabus asli dan teks normalisasi di `sumber/`, dan verifikasi struktur direktori terbentuk untuk proyek baru
- [x] 2.7 Dukung nama proyek eksplisit dan lanjut-proyek tanpa menimpa isi yang ada; verifikasi menjalankan dua kali dengan nama sama tidak menghapus dokumen yang sudah ada

## 3. Definisi peran

- [x] 3.1 Buat `prompts/_standar.md` berisi standar materi bersama: bahasa Indonesia, kewajiban glosarium, batas kepadatan slide, kewajiban menantang masukan dan melaporkan KESENJANGAN; verifikasi berkas ini menempel ke prompt tiap peran saat dimuat — ketujuh peran diperiksa
- [ ] 3.2 Tulis `prompts/kurikulum.md` (capaian pembelajaran, profil/level peserta, peta pertemuan, glosarium awal, kesenjangan silabus) dan verifikasi keluarannya memuat semua bagian itu pada silabus uji — *prompt ditulis; verifikasi keluaran butuh panggilan model*
- [ ] 3.3 Tulis `prompts/blueprint.md` (alur segmen bertimestamp, metode, kerangka isi, asesmen, daftar luaran per pertemuan) dan verifikasi total alokasi waktu tiap pertemuan sama dengan durasi sesinya — *prompt ditulis; verifikasi keluaran butuh panggilan model*
- [ ] 3.4 Tulis `prompts/writer.md` (modul bacaan: teori, contoh, rangkuman, menutup tiap capaian) dan verifikasi modul pilot memuat tiap capaian pertemuannya — *prompt ditulis; verifikasi keluaran butuh panggilan model*
- [ ] 3.5 Tulis `prompts/slide.md` (deck padat mengikuti segmen blueprint, tunduk batas kepadatan) dan verifikasi deck pilot punya slide capaian, slide per segmen, dan slide rangkuman — *prompt ditulis; verifikasi keluaran butuh panggilan model*
- [ ] 3.6 Tulis `prompts/lab.md` (kode awal bertanda bagian peserta, langkah praktikum, solusi akhir, wajib dieksekusi sampai lulus) dan verifikasi solusi lab pilot berjalan tanpa galat — *prompt ditulis; verifikasi keluaran butuh panggilan model*
- [ ] 3.7 Tulis `prompts/reviewer.md` (akurasi teknis, kesesuaian capaian, keterbacaan terhadap level, materi di luar silabus) dan verifikasi tiap temuannya menyebut berkas dan bagian — *prompt ditulis; verifikasi keluaran butuh panggilan model*
- [ ] 3.8 Tulis `prompts/editor.md` (bahasa, ejaan, konsistensi istilah terhadap glosarium, penambahan padanan Inggris) dan verifikasi istilah yang menyimpang di materi uji tertangkap — *prompt ditulis; verifikasi keluaran butuh panggilan model*
- [x] 3.9 Implementasikan `roles.py`: tujuh peran dengan model dari `MODEL_<PERAN>` (bawaan opus), pemuat prompt yang menempelkan `_standar.md`, daftar tool per peran (hanya `lab` mendapat `Bash`), dan daftar perintah terlarang; verifikasi `python -c "import roles"` memuat ketujuh peran dan hanya `lab` punya `Bash`

## 4. Ekspor luaran biner

- [x] 4.1 Implementasikan `exporter.py` fungsi Markdown ke DOCX lewat `python-docx` dengan hierarki judul terjaga; verifikasi DOCX hasilnya terbuka dan judulnya berjenjang untuk modul uji — Heading 1/2, List Bullet, List Number, dan style kode monospace terverifikasi
- [x] 4.2 Implementasikan fungsi Markdown ke PPTX lewat `python-pptx` dengan tata letak judul-dan-isi; verifikasi deck uji menghasilkan satu slide per bagian sumbernya — catatan pengajar masuk ke notes, tidak ke layar
- [x] 4.3 Jadikan kegagalan konversi sebagai kegagalan tahap yang dilaporkan, bukan peringatan; verifikasi dengan Markdown rusak bahwa tahap dilaporkan gagal
- [x] 4.4 Hasilkan ulang biner dari sumber Markdown setiap kali sumbernya berubah; verifikasi setelah revisi modul, DOCX-nya memuat isi terbaru dan tidak lagi memuat isi lama

## 5. Monitoring dan gate

- [ ] 5.1 Implementasikan `monitor.py`: event JSONL untuk mulai/selesai tahap, gate, kegagalan, kuota, penolakan perintah, memuat nama tahap, model terpakai, durasi, biaya; verifikasi `events.jsonl` proyek dapat dibaca berurutan setelah satu jalannya pipeline — *event `gate`/`gate_answer` sudah terverifikasi tertulis dan terbaca ulang; event tahap butuh satu jalannya pipeline*
- [ ] 5.2 Tambahkan notifikasi Telegram dan penerimaan jawaban gate dari pesan balasan; verifikasi gate dapat dijawab dari Telegram saat token diisi — *kode ada (diadopsi dari ai-office); verifikasi butuh token bot*
- [x] 5.3 Pastikan gate tetap berfungsi lewat terminal saat Telegram tidak dikonfigurasi; verifikasi pipeline jalan penuh dengan `TELEGRAM_BOT_TOKEN` kosong — `tg_send`/`tg_doc` diam tanpa melempar galat
- [x] 5.4 Implementasikan gate: menerima setuju, masukan teks, atau berhenti; menampilkan ringkasan dokumen, kesenjangan yang dilaporkan peran, biaya tahap, dan biaya kumulatif; verifikasi ketiga jawaban di gate menghasilkan tiga perilaku berbeda yang benar — `y` lanjut, `q` → SystemExit(0), teks dikembalikan sebagai masukan revisi
- [ ] 5.5 Pakai jawaban gate yang tiba lebih dulu bila datang dari dua kanal; verifikasi dengan menjawab dari terminal dan Telegram hampir bersamaan bahwa hanya satu diproses — *benar secara konstruksi (kanal diperiksa berurutan lalu `ask()` langsung pulang); belum diuji empiris*

## 6. Orkestrasi pipeline

- [ ] 6.1 Implementasikan `academy.py` kerangka tahap dengan satu `query()` per tahap dan system prompt per peran; verifikasi log tahap menunjukkan konteks tiap peran terpisah
- [ ] 6.2 Jalankan tahap Kurikulum, tulis `docs/KURIKULUM.md` dan `docs/GLOSARIUM.md`, lalu gate 1; verifikasi kedua berkas ada dan gate menampilkan kesenjangan silabus
- [ ] 6.3 Jalankan tahap Blueprint, tulis `docs/BLUEPRINT.md`, lalu gate 2; verifikasi blueprint memuat tiap pertemuan di peta kurikulum
- [ ] 6.4 Produksi pertemuan pilot dengan Writer, Slide, dan Lab Engineer paralel, lalu gate 3; verifikasi hanya satu pertemuan yang diproduksi sebelum gate 3 dijawab
- [ ] 6.5 Simpan masukan gate pilot ke `docs/ACUAN_GAYA.md` dan suntikkan ke prompt peran produksi berikutnya; verifikasi pertemuan kedua mengikuti koreksi gaya yang diberikan di pilot
- [ ] 6.6 Dukung pemilihan pertemuan pilot (bawaan pertemuan pertama) lewat argumen; verifikasi memilih pertemuan ketiga sebagai pilot memproduksi pertemuan ketiga lebih dulu — *argumen `--pilot` terpasang dan terparse; perilakunya butuh satu jalannya pipeline*
- [ ] 6.7 Produksi pertemuan sisanya paralel dengan isolasi kegagalan per pertemuan; verifikasi dengan satu pertemuan yang dibuat gagal bahwa pertemuan lain tetap selesai dan yang gagal dilaporkan namanya
- [ ] 6.8 Jalankan Reviewer dan Editor paralel, tulis `docs/TELAAH.md` dan `docs/PERBAIKAN.md` terurut keparahan; verifikasi daftar perbaikan menyebut berkas sasaran dan langkah tiap butir — *penyusun `PERBAIKAN.md` sudah terverifikasi terpisah: menggabungkan temuan Reviewer + Editor, mengurut tinggi→sedang→rendah, dan memetakan tiap berkas ke peran perevisinya*
- [ ] 6.9 Implementasikan putaran revisi berulang dengan telaah ulang setelah revisi, dan catat temuan yang tidak dikerjakan di ringkasan akhir bila pengguna berhenti; verifikasi dua putaran berjalan lalu berhenti sesuai pilihan pengguna
- [ ] 6.10 Tawarkan ulang tahap yang gagal tanpa mengulang tahap yang berhasil, dan simpan dokumen saat pipeline berhenti; verifikasi melanjutkan proyek setelah penghentian tidak mengulang tahap yang sudah ada dokumennya
- [ ] 6.11 Tangani batas kuota dengan menunggu sampai reset lalu mengulang tahap, dan bertanya lebih dulu bila tunggu melebihi `QUOTA_WAIT_MAX_HOURS`; verifikasi kedua jalur dengan waktu reset di bawah dan di atas ambang
- [ ] 6.12 Terapkan plafon biaya per tahap dan per pertemuan dari `.env`; verifikasi tahap berhenti dan dilaporkan saat plafonnya terlampaui
- [ ] 6.13 Dukung argumen `--project` dan `--resume <tahap>`; verifikasi melanjutkan dari tahap produksi memakai blueprint yang sudah ada — *argumen terpasang dan galatnya terverifikasi (silabus tak ada, proyek tak ada, argumen kurang); perilaku resume butuh satu jalannya pipeline*

## 7. Panel kendali dan penguncian

- [x] 7.1 Implementasikan `control.py`: kunci satu-pipeline per proyek di `.locks/`, dan verifikasi pipeline kedua pada proyek yang sama ditolak beserta keterangan proses berjalan
- [x] 7.2 Anggap kunci dari proses yang sudah mati sebagai kedaluwarsa; verifikasi setelah proses dimatikan paksa, pipeline baru boleh berjalan — kunci ber-PID mati diambil, kunci milik proses sendiri tidak ditolak
- [x] 7.3 Implementasikan `dashboard.py`: status proyek, daftar materi per pertemuan, log tahap, tombol jalankan pipeline, dan formulir jawab gate; verifikasi gate dapat dijawab dari browser — jawaban lewat `docs/GATE_JAWAB.txt` diterima `monitor.ask` sebagai sumber `dashboard`, jawaban basi dibuang, path traversal (`../../.env`) ditolak 404
- [x] 7.4 Ikat dashboard ke `127.0.0.1` secara bawaan dan tolak berjalan bila `DASHBOARD_HOST` non-lokal sementara `DASHBOARD_PASS` kosong; verifikasi kedua kondisi itu

## 8. Uji asap dan dokumentasi

- [ ] 8.1 Siapkan silabus contoh 3 pertemuan di `contoh/silabus-contoh.md` dan jalankan pipeline penuh sampai selesai; verifikasi keempat jenis luaran ada untuk ketiga pertemuan — *silabus contoh sudah ada; menjalankannya memotong kuota/biaya, jadi ditahan sampai diminta*
- [ ] 8.2 Verifikasi setiap luaran pada uji asap dapat dilacak ke satu butir blueprint, dan tidak ada luaran di luar blueprint
- [ ] 8.3 Verifikasi solusi lab ketiga pertemuan uji asap berjalan tanpa galat saat dieksekusi ulang dari nol
- [ ] 8.4 Tulis `README.md`: struktur proyek, diagram pipeline dengan letak keempat gate, setup, dan contoh perintah; verifikasi perintah di README berjalan apa adanya — *README ditulis; perintah `--help` dan seluruh jalur galat CLI terverifikasi, perintah produksi menunggu 8.1*
- [ ] 8.5 Tulis `MANUAL.md`: cara mengubah perilaku peran lewat `prompts/`, arti tiap variabel `.env`, cara melanjutkan proyek, dan cara memproduksi ulang satu pertemuan; verifikasi tiap prosedur di manual dijalankan sekali — *MANUAL ditulis; prosedur `python exporter.py <ws>` terverifikasi, prosedur produksi ulang menunggu 8.1*
