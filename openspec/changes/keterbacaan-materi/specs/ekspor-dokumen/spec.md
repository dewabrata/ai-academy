# Spec Delta

## ADDED Requirements

### Requirement: Blok kode DOCX terlihat sebagai blok
Sistem SHALL memberi paragraf blok kode di DOCX latar belakang abu muda, garis
tepi kiri, dan indent, selain font lebar tetap.

#### Scenario: Handbook dibuka di Word
- **WHEN** pembaca membuka `HANDBOOK.docx`
- **THEN** blok kode terbedakan dari paragraf di sekitarnya tanpa perlu membandingkan fontnya

### Requirement: Inline code tetap bertanda di DOCX
Sistem SHALL mempertahankan teks di antara backtick sebagai run berfont lebar
tetap saat mengubah Markdown menjadi DOCX. Penanda backtick MUST NOT dibuang
tanpa mengganti formatnya.

#### Scenario: Nama berkas di tengah kalimat
- **WHEN** sebuah paragraf menyebut `docker-compose.yml` di antara backtick
- **THEN** di DOCX nama berkas itu tampil berfont lebar tetap, bukan sebagai teks biasa

### Requirement: Penanda bahasa dipertahankan pembaca dashboard
Sistem SHALL mempertahankan penanda bahasa blok kode saat merender Markdown di
pembaca dashboard, dan MUST menandai blok keluaran secara berbeda dari blok
perintah.

#### Scenario: Membaca point di dashboard
- **WHEN** pembaca membuka sebuah point di tab Materi
- **THEN** tiap blok kode menampilkan bahasanya, dan blok `text` terlihat berbeda dari blok `bash`
