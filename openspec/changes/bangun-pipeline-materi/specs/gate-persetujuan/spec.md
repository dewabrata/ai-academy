# Spec Delta

## Purpose

Menahan pipeline di titik-titik kunci untuk meminta keputusan manusia, sehingga
rencana dan gaya materi disepakati sebelum biaya produksi besar dikeluarkan,
dan keputusan itu dapat diberikan dari terminal, dashboard, maupun Telegram.

## ADDED Requirements

### Requirement: Gate menahan pipeline sampai ada keputusan manusia
Sistem SHALL menahan pipeline di tiap gate sampai pengguna memutuskan, dan MUST
menerima tiga bentuk keputusan: menyetujui, memberi masukan untuk revisi, atau
menghentikan pipeline.

#### Scenario: Pengguna menyetujui
- **WHEN** pengguna menyetujui dokumen di sebuah gate
- **THEN** pipeline melanjut ke tahap berikutnya

#### Scenario: Pengguna memberi masukan
- **WHEN** pengguna memberi masukan berupa teks
- **THEN** dokumen itu direvisi sesuai masukan, lalu gate yang sama ditanyakan
  lagi, dan ini berulang tanpa batas jumlah putaran

#### Scenario: Pengguna menghentikan
- **WHEN** pengguna memilih berhenti
- **THEN** pipeline berhenti, dan seluruh dokumen yang sudah dihasilkan tetap
  tersimpan di ruang kerja sehingga proyek dapat dilanjutkan nanti

### Requirement: Letak gate wajib
Sistem SHALL menempatkan gate setelah dokumen kurikulum, setelah blueprint,
setelah pertemuan pilot selesai diproduksi, dan setelah tiap putaran telaah
mutu.

#### Scenario: Urutan gate
- **WHEN** pipeline berjalan dari awal sampai akhir tanpa penghentian
- **THEN** pengguna ditanya di empat titik itu, dalam urutan tersebut

#### Scenario: Gate pilot mendahului produksi massal
- **WHEN** gate pertemuan pilot belum disetujui
- **THEN** sistem MUST tidak memproduksi pertemuan lain mana pun

### Requirement: Gate dapat dijawab dari jarak jauh
Sistem SHALL menerima jawaban gate dari terminal, dari dashboard web lokal, dan
dari Telegram bila Telegram dikonfigurasi.

#### Scenario: Gate dijawab dari Telegram
- **WHEN** Telegram dikonfigurasi dan pipeline mencapai sebuah gate
- **THEN** sistem mengirim notifikasi berisi ringkasan dokumen dan menerima
  jawaban dari pesan balasan

#### Scenario: Telegram tidak dikonfigurasi
- **WHEN** Telegram tidak dikonfigurasi
- **THEN** gate tetap berfungsi lewat terminal dan dashboard tanpa galat

#### Scenario: Jawaban datang dari dua kanal sekaligus
- **WHEN** jawaban untuk gate yang sama datang dari lebih dari satu kanal
- **THEN** sistem memakai jawaban yang tiba lebih dulu dan mengabaikan sisanya

### Requirement: Gate menampilkan ringkasan dan kesenjangan
Setiap gate SHALL menampilkan ringkasan isi dokumen yang ditelaah beserta
kesenjangan yang dilaporkan peran terkait, sehingga pengguna tidak perlu
membuka berkasnya untuk memutuskan.

#### Scenario: Dokumen memuat kesenjangan
- **WHEN** peran yang menghasilkan dokumen melaporkan kesenjangan
- **THEN** gate menampilkan kesenjangan itu bersama ringkasannya

#### Scenario: Biaya tahap ditampilkan
- **WHEN** sebuah gate ditampilkan
- **THEN** ringkasannya memuat biaya tahap yang baru selesai dan biaya kumulatif
  proyek
