# Menyentuh sistem luar

Begitu aplikasi agentic menulis ke sistem produksi orang lain — LMS, CRM, repo,
ticketing — risikonya berubah jenis. Kesalahan tidak lagi berarti dokumen jelek;
ia berarti data orang lain rusak, dan sering tidak bisa dibatalkan.

---

## 1. Pola inti: agen merencanakan, kode mengeksekusi

Ini pembagian kerja yang paling menentukan.

```
Peran agen  ->  menulis RENCANA.json   (penilaian: nama, kalimat, bobot, urutan)
Kode biasa  ->  memvalidasi rencana    (deterministik, menolak yang tidak masuk akal)
Kode biasa  ->  mengeksekusi           (tanpa satu pun panggilan model)
```

Alasannya:

- **Eksekusi harus bisa diulang dan diperiksa.** Model yang memanggil API
  langsung bisa memanggil dua kali, melewatkan satu langkah, atau mengarang id.
- **Validasi harus pasti.** Bobot nilai yang totalnya bukan 100 adalah cacat
  yang bisa dihitung, bukan dinilai.
- **Biaya dan waktu.** Langkah mekanis tidak perlu token.

Yang diputuskan agen: hal yang butuh penilaian — nama yang enak dibaca, kalimat
instruksi, pertanyaan umpan balik, pembagian bobot yang masuk akal untuk materi
ini. Yang dikerjakan kode: semuanya yang lain.

**Validator harus menolak sebelum satu objek pun dibuat.** Rencana yang baru
ketahuan cacat di tengah eksekusi meninggalkan sistem luar dalam keadaan
setengah jadi — bentuk kerusakan yang paling merepotkan.

---

## 2. Daftar putih, dan tanpa penghapus

Server MCP sering mengekspos **seluruh** fungsi sistem. Di LMS yang dipakai
`ai-academy`: 1049 tool. Token yang dipakai biasanya milik admin.

```python
DIIZINKAN = {
    "core_course_create_courses",
    "core_course_get_categories",
    ...
}

def panggil(self, nama, arg):
    if nama not in DIIZINKAN:
        raise MoodleError(
            f"Tool '{nama}' tidak ada di daftar putih. "
            f"Tambahkan di sana lebih dulu kalau memang dibutuhkan.")
```

Dua aturan:

1. **Daftar putih memuat yang dibutuhkan saja**, dan ditambah secara sadar.
   Hook penjaga biasanya hanya mengawasi Write/Edit/Bash — tool MCP lewat tanpa
   diperiksa, jadi daftar putih inilah satu-satunya pagar.
2. **Tidak ada satu pun fungsi penghapus di kode produksi.** Objek yang salah
   dibuat lebih baik dihapus manusia lewat antarmuka sistemnya, yang meminta
   konfirmasi, daripada oleh kode yang salah menghitung id.

Konsekuensinya harus diakui di antarmuka: *"Yang terbuat tidak bisa dihapus dari
sini."* Dan karena itu, validasi di depan harus lebih ketat — nama kosong,
terlalu panjang, kembar, dan induk yang tidak ada semuanya ditolak sebelum
dikirim.

### Pengecualian untuk uji

Uji boleh menghapus objek uji miliknya sendiri, tetapi **penghapusnya
diizinkan di dalam proses uji saja**, tidak pernah ditambahkan ke daftar putih
di kode sumber:

```python
finally:
    if dibuat:
        moodle.DIIZINKAN.add("core_course_delete_categories")  # hanya di proses uji
        ...hapus...
        cek("benar-benar hilang", ...)                         # verifikasi sesudahnya
```

Beri objek uji nama yang tidak mungkin tertukar: `UJI-NAMA-APP-HAPUS-SAYA-...`.
Dan sesudah uji, periksa bahwa kode produksi tetap bersih:

```python
cek("tidak memuat penghapus",
    not any("delete" in x or "remove" in x for x in moodle.DIIZINKAN))
```

---

## 3. Pilih dari nama, bukan ketik id

Id yang diketik tangan salah dengan diam. Kategori `15` dan `51` sama-sama
diterima sistem; yang satu membuat objek di tempat yang benar, yang satu di
tempat orang lain.

- **Tampilkan daftar bernama**, ambil dari sistemnya sendiri lewat endpoint
  tersendiri (daftarnya bisa ratusan dan lambat — sisa halaman tidak perlu
  menunggunya).
- **Periksa id ada di sistem sebelum apa pun dibuat.**
- **Kalau sistemnya tidak terjawab, kembalikan ke isian manual** dengan pesan
  alasannya — sistem yang sedang bermasalah tidak boleh mengunci fitur.
- **Id tersimpan yang objeknya sudah dihapus tetap ditampilkan dan ditandai**,
  bukan lenyap diam-diam dari daftar. Kalau lenyap, sekali tekan Simpan nilainya
  terhapus tanpa disadari.

### Kolom kosong ≠ kolom tidak dikirim

Ini bug yang membuat objek nyata terbentuk di tempat yang tidak diniatkan:

```python
def _id(kunci, env):
    if kunci in body:                      # dikirim, walau kosong
        nilai = str(body.get(kunci) or "").strip()
    else:                                  # tidak dikirim sama sekali
        nilai = (os.getenv(env) or "").strip()
    return int(nilai) if nilai else 0
```

`body.get(kunci) or os.getenv(env)` **salah**: kolom yang sengaja dikosongkan
jatuh ke nilai bawaan, dan pengguna yang bermaksud "jangan pakai apa pun"
malah memakai nilai lama.

### Nilai bawaan global untuk hal yang per-proyek

Jangan. Nilai milik satu proyek yang dipasang sebagai bawaan semua proyek akan
diam-diam ikut ke proyek berikutnya. Kalau sebuah setelan memang per-proyek,
kosongkan bawaannya dan tandai opsional.

---

## 4. Keunikan, balapan, dan idempotensi

### Periksa-lalu-buat harus satu langkah berkunci

Dua permintaan berbarengan sama-sama membaca "nama ini belum ada", lalu
keduanya membuat. Kunci di antarmuka tidak menutup ini — dua tab atau satu muat
ulang tetap bisa.

```python
_KUNCI = threading.Lock()

def buat(b):
    with _KUNCI:
        return _buat_terkunci(b)     # baca daftar + periksa kembar + buat
```

Yang dikunci harus mencakup **pembacaan daftarnya juga**, bukan hanya
pembuatannya.

### Keunikan sering berlaku lebih luas daripada dugaan

Kode kursus di Moodle unik **se-sistem**, bukan per kategori. Proyek kedua yang
kebetulan menghasilkan kode yang sama lolos semua validasi lalu gagal di tengah
eksekusi dengan pesan yang tidak menyebut siapa pemakainya.

Periksa bentrok di depan, dan **sebutkan objek mana yang memakainya**:

```
Kode kursus 'X' sudah dipakai oleh 'Nama Kursus Lain' (id 158).
Ganti kode di atas — kode harus unik se-sistem, bukan hanya dalam kategori.
```

Bandingkan tanpa peduli besar-kecil huruf kalau sistemnya begitu.

---

## 5. MCP over HTTP: hal teknis yang menghabiskan waktu

Urutan percakapannya:

```
initialize -> notifications/initialized -> tools/list | tools/call
```

Yang perlu disiapkan:

- **Header**: `Authorization: Bearer <token>`, `Accept: application/json,
  text/event-stream`, dan `Mcp-Session-Id` yang dikembalikan server di balasan
  pertama.
- **Balasan bisa JSON biasa atau SSE.** Tangani keduanya:

  ```python
  if teks.lstrip().startswith(("event:", "data:")):
      for b in teks.splitlines():
          if b.startswith("data:"):
              return json.loads(b[5:].strip())
  ```

- **Muatan sering dibungkus** `{"result": ...}` satu lapis lagi di dalam hasil
  tool. Buka bungkusnya, lalu periksa `exception`/`errorcode` di dalamnya —
  banyak sistem mengembalikan HTTP 200 untuk kegagalan.
- **`tools/list` jauh lebih lambat daripada `tools/call`** dan bisa melewati
  batas waktu. Simpan daftarnya ke berkas dan pakai dari situ; sediakan
  `--segarkan` untuk mengambil ulang.
- **Periksa kesiapan sebelum eksekusi dimulai**, bukan setengah jalan:

  ```python
  def periksa_kesiapan(self):
      return sorted(DIIZINKAN - set(self.daftar_tool()))   # kosong = siap
  ```

### Pelajaran soal kemampuan sistem luar

Jangan berasumsi sebuah API bisa melakukan apa yang kelihatannya wajar. Di
Moodle, API inti **tidak bisa** membuat aktivitas kursus maupun menulis berkas
ke area modul — keduanya butuh plugin. Ini baru ketahuan setelah berjam-jam.

**Uji kemampuan lebih dulu dengan objek sekali pakai**, catat hasilnya di
dokumen, lalu bangun di atas yang terbukti. Jangan membangun di atas dugaan.

---

## 6. Rahasia

- Token dan kata sandi masuk `.env` yang **gitignored**. Jangan pernah mencetak
  isinya ke log, pesan, atau keluaran perintah.
- `.env` yang dipakai bersama antar mesin: **satu-satunya baris yang boleh
  berbeda adalah yang memang khas mesin** (alamat bind, path). Sisanya identik,
  dan verifikasi dengan sha256 — bukan dengan melihat sekilas.
- Token yang pernah lewat chat atau log dianggap bocor. Rotasi.
- Buat pengguna layanan khusus dengan hak seperlunya; jangan memakai token
  admin untuk produksi.
