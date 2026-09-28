# Proposal

## Why

Pemilik proyek membaca hasil pertemuan 1–3 proyek `silabus-kubernetes-eks-2026`
sebagai berkas `.md` dan sebagai `HANDBOOK.docx` di Word, lalu menilai dua hal:
blok kode tidak punya format khusus, dan susunan kalimatnya membingungkan.
Penelusuran menemukan keduanya punya sebab yang berbeda dan terpisah.

**Blok kode di DOCX memang tidak diberi format.** Style `KodeLab` di
`exporter.py` hanya menetapkan Consolas 9pt — tanpa latar, garis, maupun indent
— sehingga blok kode di Word hampir tidak terbedakan dari paragraf biasa. Lebih
jauh, `_bersih()` membuang backtick inline tanpa menggantinya dengan format apa
pun, jadi nama berkas, perintah, dan nilai contoh di dalam paragraf hilang
penandanya sama sekali.

**Di sumber Markdown-nya, kontrak penulisan kode tidak pernah ditetapkan.** Dari
~308 blok kode di pertemuan 1–3, 113 (37%) tidak punya penanda bahasa. Keluaran
perintah tidak pernah menjadi blok tersendiri; ia diceritakan di dalam paragraf,
sehingga pembaca tidak bisa membandingkan apa yang ia lihat di layar dengan apa
yang seharusnya muncul.

**Kalimatnya panjang karena tidak ada batas.** 368 paragraf di pertemuan 1–3
melebihi 60 kata. Penyebab terbesarnya bukan panjang paragraf itu sendiri,
melainkan empat kebiasaan yang menumpuk di dalam satu kalimat:

| Kebiasaan | Contoh dari materi |
|---|---|
| Definisi istilah disisipkan di tengah kalimat, kadang mengulang namanya | "sebuah reverse proxy (reverse proxy — komponen yang menerima semua trafik masuk lebih dulu, lalu meneruskannya ke salah satu dari beberapa backend di belakangnya) seperti nginx" |
| Rujukan ke bagian lain yang menunda informasi | "Apa yang **tidak** terjadi setelah statusnya berubah, itulah inti keterbatasan kedua" |
| Informasi trainer masuk ke teks bacaan peserta | "Segmen ini mendapat delapan menit di kelas" beserta tabel pembagiannya |
| Label tebal inline dipakai sebagai pengganti sub-judul | "**Hasil yang sebenarnya terjadi pada `docker-compose.yml` di atas:**" |

Prompt Writer saat ini mengatur kedalaman, konvensi, dan proses kerja, tetapi
tidak mengatur satu pun dari hal di atas. Yang tidak ditetapkan akan ditebak,
dan tebakannya berbeda-beda di tiap point.

## What Changes

- Writer menerima kontrak kalimat dan paragraf: satu gagasan per paragraf,
  maksimal tiga baris, satu kalimat maksimal ~25 kata, dilarang menumpuk tanda
  kurung dan em-dash di dalam kalimat.
- Writer menerima kontrak blok kode: penanda bahasa wajib, blok berkas diberi
  nama berkasnya, dan keluaran perintah ditulis sebagai blok `text` tersendiri —
  bukan diceritakan di paragraf.
- Definisi istilah keluar dari tengah kalimat, menjadi baris kutipan tersendiri
  setelah paragraf yang memakainya.
- Istilah yang menurut peta istilah blueprint menjadi wilayah point lain tetap
  diberi definisi satu kalimat, tetapi tanpa menyebut di pertemuan mana ia
  dibahas. Rujukan ke depan dan ke belakang dilarang.
- Label tebal inline diganti judul `####` yang pendek.
- Alokasi menit kelas dan pembagian di kelas / di luar kelas pindah dari teks
  point ke `point-NN.kelas.md`, yang tidak ikut ke handbook.
- Reviewer menelaah kontrak baru ini di mode point.
- `pemeriksa.py` menegakkan bagian yang bisa diperiksa mesin: penanda bahasa,
  paragraf terlalu panjang, rujukan antarpertemuan, dan keberadaan
  `point-NN.kelas.md`.
- `exporter.py` memberi blok kode DOCX latar, garis kiri, dan indent, serta
  mempertahankan inline code sebagai run monospace alih-alih membuang
  backtick-nya.
- Pembaca dashboard mempertahankan penanda bahasa blok kode dan menandai blok
  keluaran.

## Impact

- `prompts/writer.md`, `prompts/reviewer.md`
- `exporter.py`, `pemeriksa.py`, `dashboard.py`
- Materi yang sudah diproduksi tidak ditulis ulang otomatis. Perubahan ini
  berlaku untuk point yang diproduksi atau direvisi setelahnya.
