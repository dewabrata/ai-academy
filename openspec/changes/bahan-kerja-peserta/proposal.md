# Proposal

## Why

Materi yang dihasilkan pipeline menceritakan berkas kerja yang tidak pernah
diserahkan kepada peserta.

Pada proyek `silabus-standarisasi-programmer-sqa-tw-DIKA`, seluruh empat
pertemuan membangun narasi seputar satu aplikasi pengingat tagihan. Berkasnya
disebut berulang kali di handbook, lengkap dengan potongan isinya:

| Berkas yang disebut | Berapa kali | Ada di materi? |
|---|---|---|
| `tests/reminder.test.js` | 10 | tidak |
| `reminder-routes.js` | 10 | tidak |
| `reminder-scheduler.js` | 9 | tidak |
| `src/collection/app.js` | 2 | tidak |
| `reminder-aturan.js` | 3 | tidak |

Peserta membaca kode yang tidak bisa mereka buka, dan tidak punya pembanding
untuk memeriksa hasil kerjanya sendiri.

Penyebabnya ada di kontrak luaran, bukan pada peran yang lalai:

- `lab-kode` menghasilkan `lab/awal/` dan `lab/solusi/`, tetapi isinya latihan
  kecil yang berdiri sendiri — hook, generator, fixture — bukan aplikasi yang
  diceritakan materi.
- `praktik` hanya menghasilkan `PRAKTIK.md`. **Tidak ada satu pun berkas kerja.**
  Pertemuan yang pesertanya bekerja di aplikasi atau spreadsheet karena itu
  tidak pernah punya berkas awal maupun berkas hasil.

Akibatnya sama untuk dua jenis materi yang berbeda. Pelatihan aplikasi tidak
memberi kode awal dan kode benar; pelatihan spreadsheet tidak memberi berkas
rekap contoh dan hasil rapinya.

## What Changes

- Folder baru `bahan/` per pertemuan: `awal/` (keadaan awal yang dibuka
  peserta), `jadi/` (keadaan benar sesudah dikerjakan), dan `README.md`.
- `bahan/` berlaku untuk semua jenis tugas, tidak hanya `lab-kode`. Untuk
  materi aplikasi isinya kode; untuk materi spreadsheet isinya berkas data.
- Blueprint menetapkan isi `bahan/` tiap pertemuan lewat baris `Bahan:` di
  bagian `### Tugas`, atau `Bahan: tidak` kalau pertemuan itu memang tidak
  memerlukannya.
- Berkas spreadsheet ditulis peran sebagai `.csv`, lalu `exporter.py`
  menghasilkan `.xlsx` — pola yang sama dengan Markdown → DOCX yang sudah
  berjalan. Peran tetap dilarang menulis berkas biner langsung.
- `pemeriksa.py` memeriksa kelengkapan `bahan/`, dan memeriksa bahwa berkas
  yang **ditampilkan isinya** di materi benar-benar ada di `bahan/` atau `lab/`.
- Opsi proyek `ekspor_xlsx`, sejajar dengan `ekspor_docx` dan `ekspor_pptx`.

## Impact

- `prompts/blueprint.md`, `prompts/tugas.md`, `prompts/writer.md`
- `rencana.py`, `exporter.py`, `pemeriksa.py`, `opsi.py`, `setelan.py`
- `requirements.txt` bertambah `openpyxl`
- Materi yang sudah diproduksi tidak berubah sendiri; kontrak ini berlaku untuk
  produksi berikutnya.
