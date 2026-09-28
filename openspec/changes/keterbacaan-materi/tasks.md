# Tasks

## 1. Kontrak penulisan

- [x] 1.1 Tulis kontrak kalimat dan paragraf di `prompts/writer.md`
- [x] 1.2 Tulis kontrak blok kode di `prompts/writer.md`, beserta contoh ❌/✓
- [x] 1.3 Pindahkan aturan definisi istilah ke bentuk baris kutipan tersendiri
- [x] 1.4 Larang rujukan ke depan/belakang, dan atur istilah milik point lain
- [x] 1.5 Ganti label tebal inline dengan judul `####`
- [x] 1.6 Tambahkan luaran `point-NN.kelas.md` dan keluarkan menit dari teks point
- [x] 1.7 Perbarui struktur point, proses kerja, dan cek mandiri

## 2. Telaah

- [x] 2.1 Tambahkan kontrak keterbacaan ke lensa mode point di `prompts/reviewer.md`
- [x] 2.2 Pastikan butir keterbacaan tidak menaikkan jumlah putaran tanpa perlu

## 3. Penegakan mesin

- [x] 3.1 Periksa penanda bahasa tiap blok kode di `pemeriksa.py`
- [x] 3.2 Periksa paragraf melebihi batas panjang
- [x] 3.3 Periksa rujukan antarpertemuan
- [x] 3.4 Periksa keberadaan `point-NN.kelas.md`

## 4. Ekspor

- [x] 4.1 Beri blok kode DOCX latar, garis kiri, dan indent
- [x] 4.2 Pertahankan inline code sebagai run monospace
- [x] 4.3 Pertahankan penanda bahasa di pembaca dashboard

## 5. Verifikasi

- [x] 5.1 Uji deterministik untuk pemeriksaan baru
- [x] 5.2 Uji ekspor DOCX: blok kode dan inline code
- [x] 5.3 Jalankan `pemeriksa.py` pada materi lama untuk melihat pelanggaran yang tertangkap
