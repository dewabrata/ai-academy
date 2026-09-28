# Spec Delta

## ADDED Requirements

### Requirement: Satu gagasan per paragraf
Sistem SHALL menginstruksikan Writer menulis satu gagasan per paragraf, dengan
panjang maksimal tiga baris atau sekitar 60 kata. Satu kalimat MUST NOT melebihi
sekitar 25 kata, dan MUST NOT memuat lebih dari satu sisipan berupa tanda kurung
atau em-dash.

#### Scenario: Paragraf memuat beberapa gagasan
- **WHEN** Writer hendak menjelaskan sebab, akibat, dan alternatifnya sekaligus
- **THEN** ketiganya ditulis sebagai paragraf terpisah, bukan satu paragraf bersambung

#### Scenario: Kalimat bersarang
- **WHEN** sebuah kalimat memuat tanda kurung penjelas di dalam klausa yang sudah dipisah em-dash
- **THEN** kalimat itu dipecah menjadi dua kalimat pendek

### Requirement: Blok kode punya bahasa, judul, dan keluaran terpisah
Sistem SHALL mewajibkan setiap blok kode diberi penanda bahasa. Blok yang
menampilkan isi sebuah berkas MUST didahului baris yang menyebut nama berkas
itu. Keluaran perintah MUST ditulis sebagai blok tersendiri dengan penanda
`text`, dan MUST NOT hanya diceritakan di dalam paragraf.

#### Scenario: Perintah dan hasilnya
- **WHEN** sebuah langkah praktik menyuruh peserta menjalankan perintah
- **THEN** perintahnya berada di blok `bash` dan keluaran yang akan muncul berada di blok `text` tersendiri di bawahnya

#### Scenario: Blok tanpa bahasa
- **WHEN** Writer menulis blok berisi teks biasa, pesan error, atau isi berkas konfigurasi
- **THEN** blok itu tetap diberi penanda bahasa yang sesuai, sekurang-kurangnya `text`

### Requirement: Definisi istilah berdiri sendiri
Sistem SHALL meminta definisi istilah ditulis sebagai baris kutipan tersendiri
setelah paragraf yang pertama memakainya, bukan disisipkan di tengah kalimat.
Definisi MUST NOT mengulang nama istilah di dalam kurungnya sendiri.

#### Scenario: Istilah baru muncul di tengah penjelasan
- **WHEN** Writer memakai istilah teknis untuk pertama kalinya di sebuah paragraf
- **THEN** paragrafnya diselesaikan lebih dulu, lalu definisinya ditulis sebagai baris `> **Istilah** — arti` di bawahnya

### Requirement: Tanpa rujukan ke bagian lain
Sistem SHALL melarang rujukan ke depan maupun ke belakang di teks bacaan, baik
berupa penundaan informasi maupun penyebutan nomor pertemuan atau point lain.
Istilah yang menurut peta istilah blueprint menjadi wilayah point lain MUST
tetap diberi definisi satu kalimat, tanpa menyebut di mana ia dibahas.

#### Scenario: Istilah milik pertemuan lain
- **WHEN** sebuah point perlu menyebut objek yang pembahasan penuhnya milik pertemuan berikutnya
- **THEN** objek itu diberi definisi satu kalimat secukupnya, dan kalimat seperti "dipelajari penuh di pertemuan 2" tidak ditulis

#### Scenario: Penundaan informasi
- **WHEN** Writer hendak menulis bahwa sesuatu "akan dibahas di bagian berikutnya"
- **THEN** informasinya ditulis di tempat ia dibutuhkan, atau bagiannya disusun ulang

### Requirement: Judul menggantikan label tebal inline
Sistem SHALL meminta bagian berulang di dalam point diberi judul `####` yang
pendek, dan MUST melarang label tebal inline di awal paragraf sebagai pengganti
judul.

#### Scenario: Langkah praktik berulang
- **WHEN** sebuah point memuat beberapa langkah dengan bentuk yang sama
- **THEN** tiap bagiannya memakai judul `####` yang konsisten, bukan awalan tebal seperti "**Hasil yang diharapkan:**" yang panjang

### Requirement: Informasi trainer terpisah dari bacaan peserta
Sistem SHALL meminta Writer menulis alokasi menit kelas dan pembagian
di kelas / di luar kelas ke `point-NN.kelas.md`. Berkas itu MUST NOT ikut
digabung ke handbook, dan teks point MUST NOT menyebut jatah menit.

#### Scenario: Blueprint memberi jatah menit
- **WHEN** blueprint menetapkan butir `Di kelas (8 menit)` untuk sebuah point
- **THEN** Writer menuliskannya di `point-NN.kelas.md`, dan teks point-nya tidak menyebut angka delapan menit itu

### Requirement: Kontrak keterbacaan diperiksa mesin
Sistem SHALL memeriksa secara deterministik bahwa setiap blok kode di point
punya penanda bahasa, bahwa tidak ada paragraf melebihi batas panjang, bahwa
tidak ada rujukan antarpertemuan, dan bahwa setiap point punya berkas
`point-NN.kelas.md`.

#### Scenario: Point melanggar kontrak
- **WHEN** sebuah point memuat blok kode tanpa penanda bahasa
- **THEN** `docs/PEMERIKSAAN.md` menandainya gagal beserta nama berkas dan jumlah pelanggarannya
