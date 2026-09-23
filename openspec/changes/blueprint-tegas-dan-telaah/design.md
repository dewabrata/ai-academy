# Design

## Context

Angka dan penelusurannya ada di `proposal.md` — Why. Semuanya berasal dari
proyek nyata `silabus-kubernetes-eks-2026`, bukan dari uji buatan.

Batasan yang mengikat:

- **Pecahan point milik pemilik proyek.** Aturan "salin point dari silabus apa
  adanya" tidak berubah. Sistem boleh memberi tahu kalau sebuah point tidak
  sepadan dengan jatah waktunya, tetapi tidak boleh memecah atau menggabungnya
  sendiri.
- **Handbook adalah bahan bacaan mandiri.** Panjangnya tidak boleh dikunci ke
  menit sesi. Yang terikat waktu hanya langkah yang dikerjakan di kelas.
- Pertemuan 1–3 proyek yang sedang berjalan sudah diproduksi. Konvensi yang
  sudah dipakai di sana tidak boleh diganti, karena materinya akan jadi tidak
  konsisten.

## Goals / Non-Goals

**Goals:**

- Keputusan yang selama ini ditebak Writer diambil sekali di blueprint.
- Blueprint sendiri ditelaah sebelum dipakai 34 point.
- Putaran telaah berhenti karena materi memang beres, bukan karena batas habis.

**Non-Goals:**

- Memangkas isi handbook. Kedalaman ditentukan pemilik proyek lewat
  `POINT_HALAMAN` dan pecahan point di silabus.
- Menghapus putaran revisi. Satu putaran revisi adalah harga wajar; yang
  dikejar adalah lebih banyak point lolos di putaran 2 dan lebih sedikit yang
  dieskalasi.
- Mengubah jumlah peran atau urutan tahap.

## Decisions

### D1. Blueprint menetapkan konvensi, bukan menulis isi

Blueprint memutuskan **aturan**: penamaan, versi, platform, penomoran, peta
istilah, artefak per point, dan batas apa yang tidak dibahas di sebuah point.
Ia tidak menulis langkah-langkahnya. Menduplikasi isi di blueprint hanya
memindahkan pekerjaan sekaligus menciptakan sumber pertentangan baru: dua
tempat yang bisa saling bertolak belakang.

### D2. Blueprint ditelaah sebelum dipakai

Blueprint dibaca semua peran di semua point, jadi kesalahannya berlipat 34
kali. Sekarang ia juga yang memikul lebih banyak keputusan (D1), sehingga
menelaahnya menjadi keharusan, bukan kemewahan. Satu panggilan Reviewer mode
`blueprint` sebelum gate, ±$1 sekali per proyek.

Hasil telaah ditampilkan di gate Blueprint, dan pemilik proyek tetap yang
memutuskan — peran Reviewer tidak boleh mengubah blueprint sendiri.

### D3. Menit hanya mengikat langkah in-class

Reviewer sebelumnya menilai "point ini dijatah 8 menit padahal isinya 12
langkah" sebagai cacat. Itu salah kaprah yang sama dengan menilai buku pegangan
dari lama ceramah. Aturan barunya:

- Blueprint menandai langkah mana yang dikerjakan di kelas.
- Yang dibandingkan dengan jatah menit hanya langkah bertanda itu, dengan
  patokan kasar satu langkah perintah ±2 menit.
- Panjang prosa handbook tidak pernah dibandingkan dengan menit.

### D4. Writer menulis bertahap dan membaca ulang

Penyebab cacat konsistensi bukan jendela konteks (satu point 10–15 ribu token,
jauh di bawah kapasitas), melainkan model menulis maju terus tanpa membaca
ulang tulisannya sendiri. Karena itu: tulis per bagian, lalu **baca ulang
bagian yang sudah jadi** sebelum melanjutkan — khusus memeriksa penomoran,
istilah yang sudah dijelaskan, konvensi yang sudah dipakai, dan duplikasi.

### D5. Ambang penghambat di Reviewer

Butir di putaran 2 dan 3 selalu baru, tidak pernah mengulang. Artinya selama
tiap butir sekecil apa pun menahan point, ekornya tidak akan habis. Yang
menahan sekarang hanya:

- kesalahan teknis yang akan diajarkan sebagai kebenaran,
- pertentangan dengan point lain atau dengan blueprint,
- capaian point yang tidak tercapai.

Sisanya tetap ditulis, tetapi di bagian yang tidak menahan. Pemilik proyek tetap
melihatnya di gate pertemuan.

### D6. Fact-Checker hanya untuk klaim produk

491 klaim Benar berbanding 25 yang perlu tindakan menunjukkan jaringnya terlalu
lebar. Yang dikeluarkan dari cakupan:

- **Konvensi kelas fiktif** yang ditetapkan blueprint — itu keputusan
  penyelenggara, bukan fakta yang bisa diverifikasi.
- **Teks keluaran perintah persis** — tidak ada di dokumentasi mana pun.
  Ditulis sebagai contoh keluaran, dan kebenarannya dipastikan dengan
  menjalankannya (peran Tugas), bukan dengan membaca dokumentasi.

### D7. Konvensi antarpoint dicatat Writer

Meski blueprint sudah menetapkan lebih banyak, akan selalu ada keputusan kecil
yang muncul saat menulis. Writer mencatatnya di `point-NN.konvensi.md` (5–10
baris), dan Writer berikutnya membaca semua berkas itu — ringkas, bukan seluruh
point sebelumnya.

Kalau setelah beberapa pertemuan tidak ada lagi temuan pertentangan antarpoint,
bagian ini bisa dicopot supaya tidak menambah token tiap panggilan.

## Risks / Trade-offs

- **Blueprint lebih panjang → token masukan naik di setiap panggilan peran.**
  Diterima: blueprint beberapa KB jauh lebih murah daripada satu putaran revisi.
- **Ambang penghambat (D5) dan penyempitan Fact-Checker (D6) menurunkan
  ketelitian.** Diukur dengan skor tersembunyi Reviewer; kalau rata-rata turun
  di bawah 3,5, keduanya dibatalkan lebih dulu, bukan yang lain.
- **Telaah blueprint bisa keliru juga.** Karena itu ia hanya melaporkan; yang
  memutuskan tetap pemilik proyek di gate.

## Migration Plan

Proyek berjalan memakai prompt baru pada tahap berikutnya. Untuk
`silabus-kubernetes-eks-2026`, konvensi yang sudah dipakai pertemuan 1–3 tidak
diubah; blueprint hanya dilengkapi untuk hal yang belum pernah ditetapkan.
