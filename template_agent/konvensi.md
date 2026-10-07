# Konvensi kode, uji, dan deploy

---

## 1. Penamaan dan bahasa

`ai-academy` menulis **kode dan komentar dalam Bahasa Indonesia**: nama fungsi,
variabel, kunci JSON, pesan galat. Alasannya bukan selera — pemilik proyek dan
pembaca materinya berbahasa Indonesia, dan pesan galat di antarmuka langsung
dibaca pengguna tanpa diterjemahkan.

Aturannya kalau mengikuti pola ini:

- **Konsisten.** Jangan campur `def buat_kursus()` dengan `def create_course()`.
- **Istilah teknis yang tidak punya padanan tetap dipakai apa adanya**: `commit`,
  `hook`, `lock`, `resume`, `token`. Menerjemahkannya justru menyulitkan.
- **Nama berkas dan kunci API sistem luar tidak diterjemahkan.**
  `core_course_create_courses` tetap begitu.
- **Pesan galat ditulis untuk yang membacanya**, dan menyebut jalan keluarnya:

  ```
  Kategori id 99999 tidak ada di Moodle.
  Kode kursus 'X' sudah dipakai oleh 'Nama Lain' (id 158). Ganti kode di atas —
  kode harus unik se-sistem, bukan hanya dalam kategori.
  ```

Kalau proyek barunya berbahasa Inggris, pakai Inggris — yang penting satu
bahasa saja.

---

## 2. Komentar: tulis *kenapa*, bukan *apa*

Kode sudah mengatakan apa yang ia lakukan. Komentar dipakai untuk hal yang tidak
terlihat dari kode: keputusan, alternatif yang ditolak, dan kejadian yang
melahirkannya.

Bentuk yang dipakai:

```python
# Pesan TERAKHIR memuat kepala dan ekor sekaligus, jadi ruang untuk keduanya
# harus disisihkan - bukan yang terpanjang saja. Dengan max(), pesan terakhir
# bisa 100+ karakter melewati batas, terpotong di tengah <code> pada ekor, dan
# ditolak Telegram dengan 400. Akibatnya pertanyaan gate tidak pernah sampai.
jatah = BATAS_PESAN - len(kepala) - len(ekor) - 60
```

Tiga tempat yang wajib berkomentar:

1. **Kode yang terlihat berlebihan tetapi tidak.** Kunci, pemeriksaan ganda,
   pembacaan ulang `.env` — tanpa komentar, orang berikutnya akan membuangnya.
2. **Batas dan angka ajaib.** Dari mana `3900`? Kenapa `2` perbaikan bentuk?
3. **Keputusan arsitektur di docstring modul.** Tiap modul `ai-academy` dibuka
   dengan penjelasan apa yang ia pegang dan kenapa ia terpisah.

Yang **tidak** perlu dikomentari: hal yang sudah jelas dari nama fungsi.

---

## 3. Pola uji

Uji di proyek ini bukan pytest, melainkan skrip mandiri yang mencetak baris
`ok` / `GAGAL` dan keluar dengan kode status. Sederhana, bisa dijalankan satu per
satu, dan keluarannya langsung terbaca.

```python
gagal = 0

def cek(nama, kondisi, info=""):
    global gagal
    print(("  ok   " if kondisi else "  GAGAL") + f" {nama}"
          + (f" - {info}" if info and not kondisi else ""))
    gagal += not kondisi

...
print("SEMUA LULUS" if not gagal else f"{gagal} GAGAL")
sys.exit(1 if gagal else 0)
```

### Aturan uji

- **Pisahkan uji offline dari uji yang menyentuh layanan hidup.** Yang menyentuh
  layanan hidup hanya dijalankan kalau diminta eksplisit.
- **Sumbat jalur berbahaya sebelum menguji validasi di depannya.** Kalau
  validasinya bocor, ujinya gagal dengan pesan jelas alih-alih membuat objek
  sungguhan:

  ```python
  def jangan_unggah(*a, **k): raise Disumbat("validasi bocor: unggah() terpanggil")
  moodle_unggah.unggah = jangan_unggah
  ```

- **Objek uji di sistem luar dihapus di `finally`, lalu diverifikasi hilang.**
- **Tiru balapan dengan `threading.Barrier`**, jangan berurutan — dua pemanggilan
  berurutan tidak akan pernah menangkap bug periksa-lalu-buat:

  ```python
  mulai = threading.Barrier(2)
  def tekan():
      mulai.wait()                  # berangkat bersamaan
      hasil.append(buat({...}))
  ```

- **Uji menyebut gejala aslinya di komentar.** Pembaca berikutnya harus tahu
  kenapa uji itu ada, bukan hanya apa yang ia periksa.
- **Uji perilaku, bukan ejaan markup.** `'<select id="mdKat">'` gagal begitu
  sebuah atribut ditambahkan. Pakai `'<select id="mdKat"'`.
- **Jalur relatif, bukan absolut**, kalau uji akan ikut ke repo.

### Hal yang layak diuji di aplikasi agentic

- Setiap peran terdaftar **luarannya benar-benar diminta** di suatu tempat
  (lihat jebakan F6).
- Daftar putih tool tidak memuat penghapus.
- Validator menolak rencana cacat — satu kasus per jenis cacat.
- Pemeriksa deterministik menangkap pelanggaran yang memang dirancang ditangkap.
- Pesan notifikasi tidak melewati batas panjang, untuk isi sungguhan terpanjang.
- Bug yang pernah terjadi, satu uji masing-masing.

---

## 4. Struktur repo

```
academy.py          orkestrasi pipeline: tahap, loop, gate, resume
roles.py            definisi peran: model, prompt, tool
prompts/            satu .md per peran + _standar.md yang berlaku untuk semua
hooks_sdk.py        hook penegak aturan
pemeriksa.py        pemeriksa deterministik (tanpa panggilan model)
monitor.py          event log, status, notifikasi, kanal gate
control.py          menjalankan & menghentikan pipeline, lock, arsip
dashboard.py        HTTP server + antarmuka
exporter.py         sumber Markdown -> berkas hasil
<sistem>.py         klien sistem luar + daftar putih
<sistem>_unggah.py  validasi rencana + eksekusi (tanpa panggilan model)
workspace/          hasil kerja per proyek (gitignored)
.locks/             lock per proyek (gitignored)
.env                rahasia (gitignored)
uji/                uji
template_agent/     dokumen ini
```

Prinsip pemisahannya: **satu modul = satu tanggung jawab yang bisa disebutkan
dalam satu kalimat.** Kalau sebuah modul butuh dua kalimat, ia harus dipecah —
itu yang melahirkan `slide_desain.py` terpisah dari `exporter.py`: yang satu
memegang keputusan rupa, yang lain mengurus isi.

---

## 5. Deploy

### Prinsip

**Server staging biasanya sudah dipakai orang lain.** Survei dulu, ubah
belakangan, dan buktikan yang lain tidak terganggu.

### Urutan yang dipakai

```bash
# 1. Survei - tidak mengubah apa pun
ss -tulpn | grep LISTEN              # port yang dipakai + pemiliknya
docker ps --format '{{.Names}}\t{{.Ports}}'
python3 -V; node -v; git --version   # prasyarat
ufw status; df -h; free -h

# 2. Pasang - tanpa menyentuh direktori sistem
git clone <repo> ~/app && cd ~/app
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
npm config set prefix ~/.npm-global  # tanpa sudo
npm install -g <cli>@latest

# 3. Layanan - systemd USER service
#    ~/.config/systemd/user/<app>.service ; /etc/systemd tidak disentuh
systemctl --user daemon-reload
sudo loginctl enable-linger <user>   # hidup lagi setelah reboot
systemctl --user enable --now <app>

# 4. Verifikasi
ss -tulpn | grep ":<port>"           # port yang ditambahkan, hanya satu
docker ps                            # aplikasi lain masih Up
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/
```

### Isi unit yang penting

```ini
[Service]
WorkingDirectory=/home/<user>/app
EnvironmentFile=/home/<user>/app/.env
Environment=PATH=/home/<user>/.npm-global/bin:/usr/local/bin:/usr/bin:/bin

# Pekerjaan dilepas ke sesi sendiri supaya restart control plane tidak ikut
# membunuhnya - satu satuan kerja bisa berjam-jam dan puluhan dolar.
KillMode=process
Restart=on-failure
```

### Keamanan bind

Bawaannya `127.0.0.1`, akses lewat SSH tunnel. Kalau panel bisa menjalankan
pekerjaan yang punya akses Bash, membukanya ke jaringan berarti **login panel
itu satu-satunya pagar**. Katakan ini sekali, jelas, lalu ikuti keputusan
pemiliknya — itu servernya.

Kalau memang dibuka, wajib ada kata sandi. Kode sebaiknya **menolak jalan** di
alamat non-lokal tanpa kata sandi, bukan sekadar memperingatkan.

### Memverifikasi deploy

Jangan berhenti di "git pull berhasil".

| Yang diperiksa | Caranya |
|---|---|
| Kode ada di disk | `git log --oneline -1`, `git status --porcelain` |
| Prasyarat terpasang | versi terpasang vs versi terbaru |
| Layanan hidup | `systemctl --user is-active` |
| Mengikat alamat yang benar | `ss -tulpn \| grep ":<port>"` |
| **Proses memakai kode baru** | bandingkan isi yang disajikan dengan isi berkas |
| Aplikasi lain utuh | status container + endpoint mereka menjawab |

Baris kelima yang paling sering dilewatkan. Lihat [jebakan.md](jebakan.md#d1-proses-yang-berjalan-memegang-kode-lama).

---

## 6. Git

- **Commit dan push hanya saat diminta.**
- Pesan commit: baris pertama menyebut **akibatnya**, bukan berkasnya. Badan
  pesan menjelaskan **gejala → akar masalah → yang diubah**:

  ```
  Gate Telegram: pertanyaan hilang karena pesan terakhir melewati batas

  Di staging berkas terkirim, pertanyaannya tidak, dan log hanya berbunyi
  "telegram gagal: HTTP Error 400". Pipeline lalu menunggu jawaban atas
  pertanyaan yang tidak pernah terlihat.

  Sebabnya aritmetika jatah: ...
  ```

- **Jangan commit** `.env`, `workspace/`, `.locks/`, log, berkas cache, atau
  bahan milik klien.
- Berkas hasil yang dihasilkan ulang (deck, dokumen) tidak masuk repo.
