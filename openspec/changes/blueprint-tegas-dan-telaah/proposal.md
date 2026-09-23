# Proposal

## Why

Dari 16 point yang diproduksi proyek `silabus-kubernetes-eks-2026` (23 Sep 2026,
$121 biaya), **tidak satu pun lolos telaah di putaran pertama**: 8 point butuh 2
putaran, 8 point habis di batas 3 putaran lalu dieskalasi. Putaran revisi
memakan $48, yaitu 40% biaya proyek.

Penelusuran butir demi butir menunjukkan penyebabnya bukan Writer yang
mengabaikan catatan — **butir di putaran 2 dan 3 selalu baru, tidak pernah
mengulang**. Writer mengerjakan semua catatan, lalu teks barunya sendiri belum
pernah ditelaah dan memunculkan temuan berikutnya.

Dari 42 butir putaran 1:

| Kategori | Jumlah |
|---|---|
| Keputusan yang bisa ditetapkan blueprint (penamaan, penomoran, konvensi, struktur) | 17 |
| Butuh dijalankan untuk dipastikan (keluaran perintah, perilaku tool) | 15 |
| Keputusan penyelenggara | 2 |
| Nada dan gaya | 1 |

Artinya 40% temuan berasal dari **keputusan yang belum pernah diambil siapa
pun**, lalu ditebak Writer berbeda-beda di tiap point.

Dua temuan lain yang memperkuat:

- **Blueprint tidak pernah ditelaah siapa pun** kecuali pemilik proyek di gate,
  padahal ia dibaca semua peran. Satu kesalahannya menyebar ke seluruh point:
  jatah "8 menit untuk 12 langkah" dilaporkan berulang oleh Reviewer di banyak
  point, dan Writer tidak berwenang memperbaikinya.
- **Reviewer menilai panjang handbook terhadap menit sesi.** Itu keliru:
  handbook adalah bahan bacaan mandiri, bukan naskah yang dibacakan di kelas.
  Yang boleh terikat waktu hanya langkah yang dikerjakan di kelas.
- **Fact-Checker terlalu luas cakupannya**: 491 klaim dinyatakan Benar
  berbanding 25 yang perlu tindakan, termasuk memverifikasi teks keluaran
  perintah dan konvensi kelas fiktif yang mustahil ada di dokumentasi mana pun.

## What Changes

- **Blueprint menetapkan konvensi operasional** yang selama ini ditebak Writer:
  platform utama beserta bentuk perintah alternatifnya, penamaan lengkap
  (namespace, repository, tag, nama berkas artefak), versi yang dipatok atau
  ditulis sebagai placeholder, data contoh tunggal, skema penomoran langkah,
  dan peta istilah (di point mana tiap istilah kunci diperkenalkan).
- **Blueprint per point juga menetapkan**: apa yang TIDAK dibahas di point itu
  beserta point tujuannya, daftar langkah yang dikerjakan di kelas beserta
  jatah menitnya, artefak yang dihasilkan peserta, dan prasyarat dari point
  sebelumnya.
- **Tahap telaah blueprint** sebelum gate Blueprint: mode baru peran Reviewer
  yang memeriksa kelengkapan konvensi, pertentangan internal, dan kesepadanan
  jatah menit terhadap jumlah langkah in-class.
- **Menit hanya mengikat langkah in-class.** Reviewer dilarang menilai panjang
  handbook terhadap durasi sesi.
- **Writer menulis bertahap** dan membaca ulang bagian yang sudah ditulis
  sebelum melanjutkan, untuk menjaga penomoran, istilah, dan konvensi tetap
  konsisten di tulisan panjang — tanpa memangkas isi.
- **Writer mencatat konvensi baru** yang terpaksa ia putuskan ke
  `point-NN.konvensi.md`, dan Writer berikutnya membacanya.
- **Reviewer diberi ambang penghambat**: hanya kesalahan teknis, pertentangan
  dengan point lain, dan capaian yang tidak tercapai yang menahan point.
  Sisanya dicatat tanpa memaksa putaran baru.
- **Fact-Checker dipersempit** ke klaim perilaku produk, versi, batas, dan
  harga. Konvensi fiktif yang ditetapkan blueprint dinyatakan sah, dan teks
  keluaran perintah tidak diverifikasi ke dokumentasi.
- **Pemeriksa deterministik** memeriksa jatah menit per point dan kesepadanannya
  dengan jumlah langkah in-class.
- **Prompt Tugas** diberi aturan pengecoh quiz yang masuk akal.

## Capabilities

### New Capabilities

- `perencanaan-tegas`: konvensi operasional di blueprint dan telaah blueprint.
- `konsistensi-penulisan`: penulisan bertahap, konvensi antarpoint, ambang
  penghambat, dan cakupan verifikasi fakta.

## Impact

- `prompts/blueprint.md`, `prompts/reviewer.md`, `prompts/writer.md`,
  `prompts/fakta.md`, `prompts/tugas.md`.
- `academy.py`: tahap telaah blueprint, prompt Writer membawa konvensi point
  sebelumnya.
- `pemeriksa.py`: pemeriksaan jatah menit per point.
- Biaya: satu panggilan Reviewer tambahan per proyek (±$1), diharapkan menghemat
  jauh lebih besar dari putaran revisi yang berkurang.
- Risiko: ambang penghambat dan penyempitan Fact-Checker menukar sedikit
  ketelitian dengan biaya. Diukur lewat skor tersembunyi Reviewer; kalau turun
  di bawah 3,5 keduanya dibatalkan lebih dulu.
