# Spec Delta

## ADDED Requirements

### Requirement: Writer menulis bertahap dan membaca ulang
Sistem SHALL menginstruksikan Writer menulis point per bagian dan membaca ulang
bagian yang sudah ditulis sebelum melanjutkan, memeriksa penomoran, istilah yang
sudah dijelaskan, konvensi yang sudah dipakai, dan duplikasi antarbagian.
Pembacaan ulang ini MUST NOT dipakai untuk memangkas isi.

#### Scenario: Penomoran bertabrakan
- **WHEN** sebuah point memakai penomoran langkah peserta dan penomoran keluaran perintah sekaligus
- **THEN** Writer menemukannya saat membaca ulang dan menyelaraskannya sebelum menyerahkan

### Requirement: Konvensi baru dicatat antarpoint
Sistem SHALL meminta Writer mencatat keputusan baru yang terpaksa ia ambil ke
`point-NN.konvensi.md`, dan MUST memberikan berkas konvensi point-point
sebelumnya kepada Writer berikutnya.

#### Scenario: Keputusan menyebar ke point berikutnya
- **WHEN** point 2 menetapkan nama berkas manifest yang belum ada di blueprint
- **THEN** point 3 memakai nama yang sama tanpa perlu menebak

### Requirement: Hanya cacat berdampak yang menahan point
Sistem SHALL menahan point hanya karena kesalahan teknis yang akan diajarkan
sebagai kebenaran, pertentangan dengan point lain atau blueprint, atau capaian
yang tidak tercapai. Catatan lain MUST tetap ditulis, tetapi tidak memaksa
putaran baru.

#### Scenario: Catatan ringan
- **WHEN** telaah hanya menemukan kalimat berlebihan dan satu duplikasi ringan
- **THEN** status point menjadi siap, dan catatan itu tetap muncul di gate pertemuan

#### Scenario: Kesalahan teknis
- **WHEN** telaah menemukan satuan resource yang salah seribu kali lipat
- **THEN** point ditahan dan direvisi

### Requirement: Verifikasi fakta dibatasi pada klaim produk
Sistem SHALL membatasi Fact-Checker pada klaim tentang perilaku produk, versi,
batas, dan harga. Konvensi fiktif yang ditetapkan blueprint MUST dianggap sah,
dan teks keluaran perintah MUST NOT diverifikasi ke dokumentasi.

#### Scenario: Konvensi kelas
- **WHEN** point menyebut repository dan tag yang ditetapkan blueprint
- **THEN** Fact-Checker tidak memeriksanya dan tidak menandainya sebagai tidak ditemukan

#### Scenario: Teks keluaran perintah
- **WHEN** point menampilkan contoh keluaran sebuah perintah
- **THEN** Fact-Checker melewatinya, dan kebenarannya menjadi urusan peran yang menjalankan perintah
