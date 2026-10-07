# Arsitektur agentic

Pola yang dipakai `ai-academy` untuk menghasilkan puluhan dokumen dari satu
berkas masukan, dengan biaya terkendali dan manusia yang tetap memutuskan.

---

## 1. Peran, bukan satu agen besar

Satu agen besar yang mengerjakan semuanya punya tiga masalah: konteksnya
tercemar antar-tugas, biayanya tidak bisa dibebankan ke tahap tertentu, dan
kegagalan satu bagian menjatuhkan seluruhnya.

**Pecah jadi peran.** Tiap peran adalah satu `query()` dengan:

```python
PERAN = dict(
    model=model_for("WRITER"),          # bisa ditimpa per peran lewat .env
    system_prompt=load("writer"),       # prompts/writer.md + prompts/_standar.md
    tools=DOC_TOOLS,                    # SELURUH tool yang tersedia bagi peran ini
)
```

Aturan yang berlaku:

- **Satu peran menulis satu jenis luaran.** Kalau sebuah peran menghasilkan dua
  jenis berkas yang kegagalannya tidak berhubungan, pecah jadi dua peran. Di
  `ai-academy`, peran APLIKASI dipisah dari TUGAS karena kegagalan membangun
  kode contoh tidak boleh menjatuhkan soal dan kunci yang sudah benar.
- **Standar yang berlaku untuk semua peran ditulis sekali** di
  `prompts/_standar.md` dan ditempelkan di belakang tiap prompt peran. Jangan
  menyalinnya ke tiap berkas prompt — nanti berubah di satu tempat saja.
- **Peran dengan `Bash` harus seminimal mungkin.** Di `ai-academy` hanya dua
  dari sepuluh, dan keduanya memang harus mengeksekusi kode untuk membuktikan
  kode itu jalan.
- **Catat model yang SEBENARNYA dipakai.** Alias seperti `opus` diterjemahkan
  CLI dan bisa berpindah saat Claude Code diperbarui:

  ```python
  if isinstance(msg, SystemMessage) and msg.subtype == "init":
      asli = msg.data.get("model")      # catat ini, bukan aliasnya
  ```

### Tabel pemilik berkas

Saat ada butir revisi, yang memperbaiki adalah **peran yang menulis berkas itu**
— bukan peran "tukang tambal" terpisah yang tidak tahu konteksnya.

```python
PEMILIK_BERKAS = {"SLIDE.md": "SLIDE", "KUNCI.md": "TUGAS", ...}

def pemilik(path):
    ...                                  # yang tidak dikenali -> peran prosa
```

Berkas yang tidak dikenali jatuh ke satu peran bawaan. Lebih baik satu butir
salah alamat daripada terlewat.

---

## 2. Tool dibatasi di `tools=`, ditegakkan di hook

Dua hal berbeda yang sering tertukar:

| Opsi | Artinya |
|---|---|
| `allowed_tools=` | Tool ini disetujui otomatis (tanpa prompt izin) |
| `tools=` | **Hanya** tool ini yang ada bagi peran |
| `disallowed_tools=` | Pola yang ditolak, mis. `Bash(rm -rf *)` |

Mengisi `allowed_tools` saja **tidak membatasi apa pun** — peran masih bisa
memakai tool lain, hanya akan diminta izin. Isi `tools=`.

Bentuk pemanggilan yang dipakai:

```python
opts = ClaudeAgentOptions(
    resume=sesi_sebelumnya,              # None kalau tahap baru
    cwd=str(ruang_kerja),
    model=model,
    system_prompt=peran["system_prompt"],
    tools=peran["tools"],                # yang tersedia
    allowed_tools=peran["tools"],        # yang disetujui otomatis
    disallowed_tools=DENY_BASH,
    permission_mode="acceptEdits",
    setting_sources=[],                  # JANGAN memuat .claude/settings.json
    max_budget_usd=plafon_tahap,
    hooks=buat_hooks(label, cwd, wilayah),
)
```

`setting_sources=[]` penting: tanpa itu, setelan dan hook dari berkas `.claude/`
milik repo ikut termuat dan perilakunya berbeda antar mesin. Konsekuensinya
**hook harus ditulis sebagai hook Python milik SDK**, bukan di
`.claude/settings.json`.

### Hook yang wajib ada

```
PreToolUse  Write|Edit : tolak tulisan di luar wilayah peran, tolak berkas biner
PreToolUse  Bash       : tolak pola terlarang (agar penolakannya TERCATAT)
PostToolUse Write|Edit : periksa luaran begitu ditulis, kembalikan temuan ke peran
```

Tiga hal yang membuat hook berguna:

1. **Alasan penolakan harus bisa ditindaklanjuti.** Bukan "ditolak", melainkan
   *"Peran ini hanya boleh menulis di `materi/pertemuan-02/`. Berkas X milik
   peran lain."*
2. **Penolakan dicatat ke event log**, bukan hanya dikembalikan ke model.
   Kalau tidak, pelanggaran berulang tidak pernah terlihat.
3. **`PostToolUse` mengembalikan temuan sebagai `additionalContext`** sehingga
   peran memperbaikinya di giliran itu juga, bukan di telaah akhir:

   ```python
   return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                  "additionalContext": pesan_temuan}}
   ```

Kasus nyata: beberapa pertemuan diproduksi bersamaan dan semuanya ingin menulis
`docs/GLOSARIUM.md` — saling menimpa. Hook menolaknya dengan menyebut jalan
keluarnya: *tulis ke `ISTILAH.md` milikmu, peran Editor yang menggabungkan.*

---

## 3. Loop produksi dan pemeriksa deterministik

Bentuk loop per satuan kerja di `ai-academy`:

```
WRITER  ->  BENTUK (pemeriksa deterministik, maks 2 perbaikan, tidak memakai putaran)
        ->  REVIEWER + FAKTA (paralel)
        ->  revisi oleh pemilik berkas
        ->  ulangi sampai bersih atau batas putaran
```

**Pemeriksa deterministik mendahului telaah model.** Yang bisa dihitung, hitung:

- jumlah butir per slide, jumlah kata per butir, jumlah baris blok kode
- berkas yang ditampilkan isinya tetapi tidak pernah diserahkan
- sintaks kode contoh (jalankan parsernya)
- kolom CSV yang tidak sama antar berkas

Alasannya bukan hemat biaya saja: pemeriksa deterministik **selalu memberi
jawaban yang sama**, sementara model bisa melewatkan hal yang sama di putaran
berikutnya.

Perbaikan bentuk **tidak boleh memakai jatah putaran telaah**. Itu koreksi
mekanis, bukan perbedaan pendapat; batasi dengan hitungan sendiri
(`BENTUK_MAKS_PERBAIKAN = 2`) lalu teruskan.

---

## 4. Gate manusia

Taruh gate di tempat yang **mahal untuk salah**, bukan di setiap langkah.
Di `ai-academy`: sesudah kurikulum (sebelum produksi dimulai) dan sesudah tiap
pertemuan selesai.

Tiga aturan gate:

1. **Tampilkan bahan keputusannya utuh, jangan dipotong.** Gate kurikulum
   menampilkan teks silabus yang benar-benar dibaca peran — itulah yang membuat
   ekstraksi PDF/DOCX yang berantakan tertangkap sebelum biaya produksi keluar.
   Memotongnya berarti manusia memutuskan tanpa melihat sebagian bahannya.
2. **Tiga pilihan, bukan dua:** setuju / berhenti / beri masukan. Tanpa opsi
   masukan, satu-satunya cara memperbaiki adalah membatalkan semuanya.
3. **Jawaban masuk lewat beberapa kanal, yang pertama tiba menang.** Lihat
   [monitoring.md](monitoring.md).

---

## 5. Plafon biaya

Dua lapis:

```python
max_budget_usd=budget("POINT_WRITER", 10.0)   # per tahap
# + plafon total proyek, diperiksa sebelum tiap tahap mulai
```

Yang harus diperhatikan:

- **`max_budget_usd=0` membuat tahap berhenti seketika.** Kalau plafonnya
  dimaksudkan "tanpa batas", kirim `None`, bukan `0`.
- **`ResultMessage` terbit sekali per subagent dan membawa total tahap, bukan
  tambahan.** Yang boleh ditambahkan ke biaya kumulatif hanya selisihnya:

  ```python
  _run_cost: dict = {}                 # biaya kumulatif terakhir per tahap
  tambahan = total_baru - _run_cost.get(label, 0)
  ```

  Tanpa ini biaya terhitung berlipat dan plafon proyek berhenti terlalu dini.
- **Plafon per tahap dapat disetel dari `.env`** (`BUDGET_WRITER=10.0`) supaya
  bisa diubah tanpa menyentuh kode.

### Eskalasi model

Saat sebuah tahap gagal, naikkan modelnya satu tingkat lalu ulangi:

```python
ESKALASI = ["haiku", "sonnet", "opus"]
```

Ini lebih murah daripada memakai model terkuat untuk semua tahap sejak awal —
kecuali untuk peran perencanaan, yang kekeliruannya terbawa ke seluruh hasil.
Di situ pakai yang terkuat sejak awal.

---

## 6. Lock, state, dan resume

### Lock

Satu pipeline per proyek. `academy.py` menulis `.locks/<proyek>.lock` berisi
PID-nya dan menghapusnya saat selesai.

```json
{"pid": 691965, "project": "nama-proyek", "action": "jalan", "started": 1790693771.8}
```

Aturan: **kunci dari proses yang sudah mati dilaporkan kedaluwarsa, tidak
diklaim diam-diam.** Yang memutuskan mengambil alih adalah pipeline, bukan
dashboard. Lock basi yang dibiarkan membuat proyek tampak sedang berjalan
selamanya — periksa PID-nya, jangan percaya keberadaan berkasnya.

### State dan resume

```python
TAHAP = ["kurikulum", "blueprint", "produksi", "akhir"]

def tulis_state(ws, tahap): (ws / "docs" / "STATE.txt").write_text(tahap)
```

Tulis state **sebelum** tahap mulai, bukan sesudah selesai. Pipeline yang mati
di tengah akan dilanjutkan dari tahap itu, bukan dari tahap sesudahnya.

Simpan juga `session_id` tiap peran, sehingga tahap yang diulang bisa
`resume=` ke sesi sebelumnya dan tidak membangun ulang konteksnya dari nol.
Saat resume, tempelkan catatan di depan prompt agar peran tahu ia melanjutkan.

### Proses terlepas dari control plane

```python
kw = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
      else {"start_new_session": True})
subprocess.Popen(cmd, stdout=log, stderr=STDOUT, stdin=DEVNULL, env=env, **kw)
```

Pipeline tidak boleh ikut mati kalau dashboard ditutup atau di-restart. Satu
satuan kerja bisa berjam-jam dan puluhan dolar.

**Baca ulang `.env` tepat sebelum spawn**, jangan sekadar mewarisi lingkungan:
dashboard bisa hidup berhari-hari, dan setelan yang diubah sesudahnya harus ikut
ke pipeline yang baru dijalankan.

---

## 7. Yang tidak boleh dilakukan agen

- **Menulis berkas biner langsung.** Agen menulis sumber Markdown; kode biasa
  yang menghasilkan `.docx` / `.pptx` / `.xlsx`. Berkas biner yang ditulis model
  hampir selalu rusak dan tidak bisa ditelaah perbedaannya.
- **Menyentuh sistem luar langsung.** Lihat [integrasi.md](integrasi.md).
- **Memasang paket ke lingkungan global** (`npm i -g`, `pip install -g`).
  Kalau sebuah tugas butuh dependensi, perencanaan yang menyebutnya dan manusia
  yang memasangnya.
