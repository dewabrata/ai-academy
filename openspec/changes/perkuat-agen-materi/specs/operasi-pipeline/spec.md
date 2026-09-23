# Spec Delta

## ADDED Requirements

### Requirement: Setiap penolakan tool tercatat
Sistem SHALL mencatat setiap pemanggilan tool yang ditolak — baik oleh daftar
perintah terlarang maupun oleh aturan penulisan — sebagai event `tool_denied`
yang memuat tahap, tool, sasaran, dan alasannya.

#### Scenario: Perintah terlarang dicoba
- **WHEN** peran Lab Engineer mencoba perintah pada daftar terlarang
- **THEN** perintah ditolak dan event `tool_denied` tercatat beserta perintahnya

#### Scenario: Penulisan di luar wilayah dicoba
- **WHEN** peran produksi mencoba menulis di luar folder pertemuannya
- **THEN** event `tool_denied` tercatat beserta path dan alasannya

#### Scenario: Jumlah penolakan terlihat
- **WHEN** satu tahap selesai
- **THEN** jumlah penolakan pada tahap itu dapat dibaca dari event log dan tampil di dashboard
