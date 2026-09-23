# Tasks

## 1. Blueprint lebih tegas

- [x] 1.1 `prompts/blueprint.md`: bagian konvensi operasional wajib (platform, penamaan, versi, data contoh, penomoran langkah, peta istilah)
- [x] 1.2 `prompts/blueprint.md`: per point wajib menyebut "tidak dibahas di sini", langkah in-class + menit, artefak peserta, prasyarat dari point sebelumnya
- [x] 1.3 Verifikasi dengan blueprint buatan: parser `rencana.py` tetap membaca point dan jenis tugas seperti semula — 18 uji baru lulus, 3 rangkaian uji lama tanpa regresi

## 2. Telaah blueprint

- [x] 2.1 `prompts/reviewer.md`: mode `blueprint` — kelengkapan konvensi, pertentangan internal, menit vs langkah in-class
- [x] 2.2 `academy.py`: jalankan telaah blueprint sebelum gate, tampilkan hasilnya di gate; penelaah tidak boleh mengubah blueprint
- [x] 2.3 Verifikasi: tahap berjalan, hasil telaah muncul di teks gate, dan wilayah tulisnya terbatas

## 3. Penulisan dan telaah point

- [x] 3.1 `prompts/writer.md`: menulis bertahap + baca ulang bagian sebelumnya; larangan memangkas isi
- [x] 3.2 `prompts/writer.md` + `academy.py`: catat `point-NN.konvensi.md`, dan Writer berikutnya membacanya
- [x] 3.3 `prompts/reviewer.md`: ambang penghambat; dilarang menilai panjang handbook terhadap menit sesi
- [x] 3.4 `prompts/fakta.md`: cakupan dipersempit ke klaim produk; konvensi blueprint sah; keluaran perintah tidak diverifikasi

## 4. Pemeriksa dan tugas

- [x] 4.1 `pemeriksa.py`: pemeriksaan alokasi menit per point dan kesepadanannya dengan langkah in-class
- [x] 4.2 `prompts/tugas.md`: aturan pengecoh quiz yang masuk akal

## 5. Uji dan ukur

- [ ] 5.1 Uji asap dengan silabus contoh (Sonnet, point pendek): tahap telaah blueprint jalan, format baru tidak merusak parser maupun pemeriksa
- [ ] 5.2 Ukur di pertemuan 4–6 proyek EKS: butir putaran 1, jumlah putaran, eskalasi, biaya per point, jumlah kata per point, skor tersembunyi
- [ ] 5.3 Batalkan 3.3 dan 3.4 lebih dulu bila skor rata-rata turun di bawah 3,5
