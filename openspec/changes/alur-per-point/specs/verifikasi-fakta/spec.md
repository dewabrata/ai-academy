# Spec Delta

## ADDED Requirements

### Requirement: Writer menandai klaim produk
Sistem SHALL menginstruksikan Writer untuk menandai setiap klaim tentang fitur,
harga, batasan, atau perilaku produk dengan `[CEK-FAKTA: <klaim>]` alih-alih
mengklaimnya benar sendiri. Writer MUST menghapus penanda itu hanya setelah
Fact-Checker menyatakan klaimnya benar, atau setelah klaimnya dikoreksi.

#### Scenario: Klaim sudah diverifikasi
- **WHEN** Fact-Checker melaporkan klaim bertanda sebagai Benar
- **THEN** pada revisi berikutnya Writer menghapus penanda dan mempertahankan klaimnya

### Requirement: Fact-Checker memverifikasi ke sumber resmi
Sistem SHALL menjalankan peran Fact-Checker yang memiliki akses WebSearch dan
WebFetch untuk memverifikasi setiap klaim bertanda dan klaim produk lain di
point. Setiap klaim MUST dilaporkan dengan format
`Klaim: "..." → Status: [Benar/Salah/Tidak ditemukan] → [Koreksi] → Sumber: <URL>`.

#### Scenario: Klaim salah
- **WHEN** dokumentasi resmi bertentangan dengan klaim di point
- **THEN** Fact-Checker melaporkan Salah beserta versi yang benar dan URL sumbernya, lalu menulis `Status: Ada koreksi`

#### Scenario: Tidak ada klaim
- **WHEN** point tidak memuat klaim produk
- **THEN** Fact-Checker menulis `Status: Tidak ada koreksi`

### Requirement: Penanda klaim tidak tersisa di materi final
Sistem SHALL memeriksa bahwa point dan handbook final tidak lagi memuat
`[CEK-FAKTA`. Setiap penanda yang tersisa MUST dilaporkan pemeriksa sebagai
kegagalan.

#### Scenario: Penanda tertinggal
- **WHEN** `HANDBOOK.md` masih memuat `[CEK-FAKTA: ...]`
- **THEN** pemeriksaan "klaim terverifikasi" gagal dan menyebut jumlah penandanya
