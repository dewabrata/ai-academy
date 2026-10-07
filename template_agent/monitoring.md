# Monitoring proses yang berjalan berjam-jam

Pipeline agentic berbeda dari request-response: satu run bisa 3 jam dan $40.
Manusia tidak duduk menunggu, tetapi harus bisa tahu keadaannya kapan saja dan
menjawab saat diminta. Tiga lapis di bawah ini yang membuatnya mungkin.

---

## 1. Tiga berkas keadaan

Semua di `docs/` milik proyek. Tanpa database, tanpa dependency di luar stdlib.

| Berkas | Isi | Dibaca siapa |
|---|---|---|
| `events.jsonl` | Riwayat lengkap, satu baris JSON per kejadian | Manusia saat menelusuri |
| `status.json` | Snapshot keadaan **sekarang** | Dashboard, tiap beberapa detik |
| `pipeline.log` | stdout/stderr mentah proses | Saat ada yang aneh |
| `STATE.txt` | Satu kata: tahap terakhir yang dimulai | Resume |

Pisahkan riwayat dari snapshot. Dashboard yang harus membaca 50 MB `events.jsonl`
untuk tahu "sedang apa sekarang" akan lambat dan membebani disk.

Jenis event yang terbukti berguna:

```
stage_start / stage_end    label, model, turns, cost, subtype
model                      alias yang diminta vs model yang benar-benar dipakai
agent                      cuplikan teks yang dikatakan peran
tool                       tool apa, sasarannya apa
tool_denied                penolakan hook + alasannya
gate                       gate dibuka, dan jawabannya saat masuk
```

`tool_denied` sering dilewatkan. Tanpa itu, pelanggaran aturan yang berulang
tidak pernah terlihat — dan prompt peran tidak pernah diperbaiki.

---

## 2. Gate: beberapa pintu, satu antrean

Manusia harus bisa menjawab dari mana pun ia sedang berada. `ai-academy` punya
tiga kanal, diperiksa berurutan tiap putaran, dan **yang pertama tiba menang**:

```python
while True:
    try:
        jawaban, asal = _stdin_q.get_nowait().strip(), "terminal"
    except queue.Empty:
        jawaban, asal = _baca_jawaban_berkas(), "dashboard"
        if not jawaban:
            jawaban, asal = _tg_poll(), "telegram"
    if jawaban:
        break
```

### Dashboard menjawab lewat berkas, bukan stdin

Pipeline sudah terlepas dari dashboard (`start_new_session`), jadi stdin-nya
tidak bisa ditulisi. Kanalnya berupa berkas:

```
dashboard  -> tulis docs/GATE_JAWAB.txt
pipeline   -> baca, lalu HAPUS berkasnya
```

Menghapus setelah terbaca itu wajib. Jawaban yang tertinggal akan dibaca lagi
oleh gate berikutnya, dan manusia menjawab sesuatu yang tidak pernah ia lihat.
Buang juga jawaban tertinggal **saat pipeline mulai**, bukan hanya saat gate
ditutup.

### Satu antrean Telegram, satu pembaca

`getUpdates` milik sebuah bot hanya punya satu antrean dan satu offset bersama.
Kalau dua proses ikut membaca, pesan tertelan di salah satunya dan hilang dari
yang lain.

**Aturannya: Telegram hanya didengarkan saat tidak ada pipeline yang berjalan.**
Dashboard berhenti polling begitu sebuah pipeline hidup.

Ini juga berarti: **jangan pernah menguji bot secara langsung selagi pipeline
berjalan.** Pesan ujimu akan diterima sebagai jawaban gate yang sesungguhnya.
Kalau dua lingkungan (laptop dan staging) memakai token bot yang sama, jangan
menjalankan pipeline di keduanya bersamaan — atau beri staging bot sendiri.

---

## 3. Notifikasi yang tidak boleh gagal diam-diam

Notifikasi memang tidak boleh menjatuhkan pipeline:

```python
except Exception as e:
    print(f"  (telegram gagal: {e})")   # jangan melempar
```

Tapi "tidak menjatuhkan" bukan berarti "boleh hilang tanpa penjelasan". Tiga
hal yang wajib:

**a. Cetak sebab sesungguhnya, bukan kelasnya.** Telegram menaruh alasan di
badan balasan; tanpa membacanya yang tercatat hanya `HTTP Error 400: Bad
Request` dan penyebabnya harus ditebak berjam-jam.

```python
sebab = str(e)
if hasattr(e, "read"):
    try: sebab = json.loads(e.read()).get("description", sebab)
    except Exception: pass
```

**b. Sediakan jalur cadangan untuk pesan yang penting.** Kalau kiriman
ber-format gagal, kirim ulang sebagai teks polos. Kehilangan format jauh lebih
ringan daripada gate yang tidak terlihat sementara pipeline menunggu jawabannya.

**c. Hormati batas panjang, dan hitung dengan benar.** Lihat
[jebakan.md](jebakan.md) — ini sumber bug yang nyata dan mahal.

### Pesan panjang dibagi, bukan dipotong

Memotong berarti manusia memutuskan tanpa melihat sebagian bahannya. Bagi jadi
beberapa pesan berurutan, dan:

- potong di pergantian baris, bukan di tengah kalimat
- **tombol hanya di pesan terakhir** — menjawab dari potongan tengah berarti
  menjawab sebelum selesai membaca
- kalau bagiannya terlalu banyak, pertahankan bagian **awal dan akhir**;
  kesimpulan dan hal yang harus diputuskan biasanya ada di ujung
- lampirkan berkas penuhnya, dan sebutkan bahwa teks lengkapnya ada di sana

---

## 4. Memantau dari luar (sesi agen)

Saat kamu — Claude — perlu menunggu proses panjang milik orang lain selesai:

- **Jangan polling dengan `sleep` berulang di foreground.** Pakai pemantau
  latar yang keluar begitu kondisinya terpenuhi.
- **Jangan menyentuh prosesnya.** Membaca daftar proses dan berkas log saja.
- **Hati-hati `pgrep -f` mencocoki dirinya sendiri.** Baris perintah pembungkus
  memuat polanya, jadi proses tampak selalu hidup. Pakai kurung siku:

  ```bash
  pgrep -f "academy[.]py"     # bukan: pgrep -f "academy.py"
  ```

- **Pastikan filter pemantau juga menangkap kegagalan**, bukan hanya
  keberhasilan. Pemantau yang hanya mencari penanda sukses akan diam seribu
  bahasa saat proses crash — dan diam itu terlihat sama persis dengan "masih
  berjalan".
- **Saat melapor, bedakan "sudah ada di disk" dari "sudah dipakai proses yang
  hidup".** Lihat aturan 12 di [README.md](README.md).

---

## 5. Umpan balik di antarmuka

Dua hal yang kelihatannya kosmetik tetapi mencegah kerusakan nyata:

**Setiap permintaan yang lambat harus terlihat sedang bekerja.** Hitung
permintaan yang sedang berjalan supaya beberapa sekaligus tetap benar:

```javascript
let SIBUK = 0;
function tandaiSibuk(d) {
  SIBUK = Math.max(0, SIBUK + d);
  document.getElementById("sibuk").hidden = SIBUK === 0;
}
```

Bungkus `fetch` dengan `try/finally` — jaringan putus tidak boleh membuat
penanda sibuk menyala selamanya.

**Tombol yang memicu kerja mengunci diri selama kerja itu berjalan**, lalu
kembali ke **keadaan semula** — bukan ke "aktif". Tombol yang memang sengaja
dimatikan (karena rencananya belum sah) tidak boleh ikut hidup hanya karena satu
permintaan selesai:

```javascript
const teks = el.textContent, matiSemula = el.disabled;
el.disabled = true; el.textContent = "sedang jalan…";
try { return await kerja(); }
finally { el.textContent = teks; el.disabled = matiSemula; }
```

Kunci di antarmuka saja **tidak cukup** untuk operasi yang membuat sesuatu —
dua tab atau satu muat ulang tetap bisa menyelinap. Lihat aturan 10.
