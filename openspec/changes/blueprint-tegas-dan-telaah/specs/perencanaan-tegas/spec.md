# Spec Delta

## ADDED Requirements

### Requirement: Blueprint menetapkan konvensi operasional
Sistem SHALL menuntut blueprint menetapkan keputusan yang dipakai seluruh point:
platform utama beserta bentuk perintah alternatifnya, penamaan (namespace,
repository, tag, nama berkas artefak), versi yang dipatok atau ditulis sebagai
placeholder, data contoh tunggal, skema penomoran langkah, dan peta istilah yang
menyebut di point mana tiap istilah kunci diperkenalkan.

#### Scenario: Konvensi lengkap
- **WHEN** blueprint selesai ditulis
- **THEN** bagian konvensi memuat keenam keputusan itu dengan nilai konkret, bukan kategori

#### Scenario: Peran produksi memakai konvensi
- **WHEN** Writer menulis point yang memerlukan nama namespace atau tag
- **THEN** ia memakai nilai dari konvensi blueprint, bukan mengarang sendiri

### Requirement: Blueprint per point menyatakan batas dan artefaknya
Sistem SHALL menuntut tiap point di blueprint menyebut apa yang TIDAK dibahas di
point itu beserta point tujuannya, daftar langkah yang dikerjakan di kelas
beserta jatah menitnya, artefak yang dihasilkan peserta, dan prasyarat dari
point sebelumnya.

#### Scenario: Batas isi point
- **WHEN** sebuah topik dibahas di dua point berdekatan
- **THEN** blueprint menyatakan point mana yang membahasnya dan point lain menyebutnya sebagai di luar cakupan

### Requirement: Blueprint ditelaah sebelum disetujui
Sistem SHALL menjalankan telaah blueprint sebelum gate Blueprint. Telaah MUST
memeriksa kelengkapan konvensi, pertentangan internal, dan kesepadanan jatah
menit terhadap jumlah langkah in-class, lalu menampilkan hasilnya di gate.
Peran penelaah MUST NOT mengubah blueprint.

#### Scenario: Jatah menit tidak sepadan
- **WHEN** sebuah point dijatah 8 menit tetapi menandai 12 langkah dikerjakan di kelas
- **THEN** telaah melaporkannya, dan laporan itu tampil di gate Blueprint sebelum produksi dimulai

#### Scenario: Blueprint sudah baik
- **WHEN** telaah tidak menemukan masalah
- **THEN** gate tetap ditampilkan dengan catatan bahwa telaah bersih

### Requirement: Jatah menit hanya mengikat langkah in-class
Sistem SHALL membandingkan jatah menit hanya dengan langkah yang ditandai
dikerjakan di kelas. Panjang prosa handbook MUST NOT dinilai terhadap durasi
sesi, karena handbook adalah bahan bacaan mandiri.

#### Scenario: Handbook panjang untuk sesi pendek
- **WHEN** sebuah point berisi 15 halaman bacaan dengan 4 langkah in-class dalam jatah 8 menit
- **THEN** tidak ada temuan soal panjang, karena yang terikat waktu hanya keempat langkah itu

### Requirement: Pemeriksa memeriksa alokasi menit per point
Sistem SHALL memeriksa bahwa tiap point memiliki jatah menit di blueprint dan
bahwa jumlah langkah in-class-nya sepadan dengan jatah itu.

#### Scenario: Point tanpa jatah menit
- **WHEN** blueprint tidak menyebut alokasi menit untuk sebuah point
- **THEN** pemeriksaan "alokasi menit per point" gagal dan menyebut point itu
