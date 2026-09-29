# Tasks

## 1. Kontrak perencanaan

- [x] 1.1 Tambahkan baris `Bahan:` ke bagian `### Tugas` di `prompts/blueprint.md`
- [x] 1.2 Urai `Bahan:` di `rencana.py`

## 2. Kontrak produksi

- [x] 2.1 Tulis kontrak `bahan/awal`, `bahan/jadi`, `bahan/README.md` di `prompts/tugas.md`
- [x] 2.2 Konvensi `.csv` untuk spreadsheet, larangan menulis biner
- [x] 2.3 `prompts/writer.md`: berkas yang ditampilkan isinya harus yang diserahkan

## 3. Ekspor

- [x] 3.1 `csv_ke_xlsx()` di `exporter.py`, tambahkan `openpyxl`
- [x] 3.2 Opsi proyek `ekspor_xlsx` di `opsi.py` dan `setelan.py`
- [x] 3.3 Konversi seluruh `.csv` di `bahan/` saat ekspor pertemuan

## 4. Pemeriksaan

- [x] 4.1 Periksa kelengkapan `bahan/` sesuai deklarasi blueprint
- [x] 4.2 Periksa berkas yang ditampilkan isinya benar-benar ada
- [x] 4.3 Periksa `.csv` terurai dan jumlah kolomnya konsisten

## 5. Verifikasi

- [x] 5.1 Uji deterministik untuk pemeriksaan baru
- [x] 5.2 Uji `csv_ke_xlsx`
- [x] 5.3 Jalankan pada materi lama untuk melihat pelanggaran yang tertangkap

## 6. Peran Aplikasi

- [x] 6.1 `prompts/aplikasi.md` dan pendaftaran di `roles.py`
- [x] 6.2 Jalankan sebagai tahap sendiri di paket pertemuan
- [x] 6.3 Pindahkan `bahan/` dari peran Tugas
- [x] 6.4 `BUDGET_APLIKASI` dan `MODEL_APLIKASI` terpisah
- [x] 6.5 Perintah `--bahan N|semua` untuk materi yang sudah jadi
- [x] 6.6 Periksa sintaks berkas di `bahan/` dan `lab/awal/`
