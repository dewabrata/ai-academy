# Spec Delta

## ADDED Requirements

### Requirement: Point diproduksi berurutan dalam loop telaah
Sistem SHALL memproduksi setiap point dalam satu pertemuan satu per satu sesuai
urutan di blueprint. Tiap point melewati Writer, lalu Reviewer dan Fact-Checker
yang berjalan paralel. Point berikutnya MUST NOT dimulai sebelum point
sebelumnya siap atau dieskalasi.

#### Scenario: Point lolos di putaran pertama
- **WHEN** Reviewer menulis `Status: Siap ditunjukkan ke user` dan Fact-Checker menulis `Status: Tidak ada koreksi` untuk point 1
- **THEN** point 1 ditandai siap dan Writer mulai menulis point 2

#### Scenario: Point butuh revisi
- **WHEN** Reviewer menulis `Status: Perlu revisi` atau Fact-Checker menulis `Status: Ada koreksi`
- **THEN** Writer merevisi point yang sama berdasarkan kedua catatan, lalu Reviewer dan Fact-Checker menelaah ulang

#### Scenario: Status tidak terbaca
- **WHEN** berkas telaah tidak ada atau tidak memuat baris `Status:` yang dikenali
- **THEN** point dianggap belum siap untuk putaran itu

### Requirement: Loop dibatasi dan dieskalasi
Sistem SHALL membatasi loop satu point paling banyak `POINT_MAKS_PUTARAN`
putaran (bawaan 3). Point yang belum siap setelah batas itu MUST ditandai
`eskalasi` dan pipeline lanjut ke point berikutnya.

#### Scenario: Point tidak siap setelah 3 putaran
- **WHEN** point masih berstatus belum siap setelah putaran ke-3
- **THEN** point ditandai eskalasi, catatan terakhirnya dicatat untuk gate pertemuan, dan point berikutnya dimulai

### Requirement: Writer menulis dengan konteks point sebelumnya
Sistem SHALL memberi Writer path point sebelumnya yang sudah siap, supaya studi
kasus dan istilah berkesinambungan. Writer juga diberi panjang target dari
`POINT_HALAMAN`.

#### Scenario: Menulis point ketiga
- **WHEN** Writer mulai menulis point 3
- **THEN** prompt-nya menyebut point 2 untuk dibaca utuh, point 1 untuk dibaca judul dan subjudulnya, dan panjang target point

### Requirement: Pilot di point pertama
Sistem SHALL berhenti di gate `PILOT` setelah point pertama pertemuan pilot
selesai diloop dan sebelum point berikutnya ditulis. Jawaban teks MUST disimpan
ke `docs/ACUAN_GAYA.md`, dan point pilot direvisi mengikuti jawaban itu.

#### Scenario: Pemilik menyetujui gaya
- **WHEN** gate PILOT dijawab `y`
- **THEN** produksi point berikutnya dimulai

#### Scenario: Pemilik mengoreksi gaya
- **WHEN** gate PILOT dijawab dengan teks koreksi
- **THEN** koreksi ditambahkan ke `docs/ACUAN_GAYA.md`, Writer merevisi point pilot, dan gate PILOT ditanyakan lagi

### Requirement: Produksi bisa dilanjutkan
Sistem SHALL melewati point yang sudah berstatus siap atau eskalasi saat pipeline
dijalankan ulang. Untuk point yang putarannya terputus, putaran dilanjutkan dari
berkas telaah terakhir.

#### Scenario: Pipeline mati di tengah point 4
- **WHEN** pipeline dijalankan ulang dengan `--resume produksi` dan point 1–3 sudah siap
- **THEN** point 1–3 tidak ditulis ulang dan produksi dilanjutkan dari point 4

### Requirement: Peran hanya punya tool miliknya
Sistem SHALL membatasi tool yang tersedia untuk setiap peran sesuai daftar
perannya. Tool di luar daftar MUST NOT dapat dipanggil, termasuk Bash untuk
peran selain Tugas.

#### Scenario: Reviewer mencoba Bash
- **WHEN** Reviewer berjalan
- **THEN** Bash tidak tersedia baginya, dan tidak ada event pemakaian Bash oleh Reviewer
