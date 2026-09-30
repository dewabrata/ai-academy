"""Monitoring: tulis event ke docs/events.jsonl + snapshot docs/status.json,
kirim notifikasi Telegram, dan terima jawaban gate dari Telegram atau terminal.
Tidak ada dependency di luar stdlib.

Disalin dari ai-office lalu disesuaikan: dua proyek ini punya daftar tahap dan
bentuk luaran yang berbeda dan keduanya masih berubah, jadi berbagi satu paket
sekarang berarti setiap perubahan di satu proyek menanggung risiko merusak yang
lain (lihat openspec/changes/bangun-pipeline-materi/design.md, keputusan D8).
"""
import asyncio
import json
import os
import queue
import re
import threading
import time
import uuid
import urllib.parse
import urllib.request
from pathlib import Path

_docs: Path | None = None
_status: dict = {}
_tg_offset = 0
# Biaya kumulatif terakhir per tahap. ResultMessage terbit sekali per subagent
# dan tiap kali membawa total tahap, bukan tambahan - jadi yang boleh
# ditambahkan hanya selisihnya.
_run_cost: dict = {}


# ---------------------------------------------------------------------------
# Init / event log
# ---------------------------------------------------------------------------
def baca_json(path: Path) -> dict:
    """Baca JSON sebagai UTF-8; berkas lama yang tertulis cp1252 tetap terbaca."""
    if not path.exists():
        return {}
    data = path.read_bytes()
    for enc in ("utf-8", "cp1252"):
        try:
            return json.loads(data.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {}


def init(docs: Path, project: str):
    global _docs, _status
    _docs = docs
    sp = docs / "status.json"
    _status = baca_json(sp)
    _status.update(project=project, updated=time.time())
    _status.setdefault("cost", {})
    _status.setdefault("quota", {})
    _save()


def _save():
    if _docs:
        _status["updated"] = time.time()
        # Wajib UTF-8: bawaan Windows cp1252 tidak punya karakter seperti panah,
        # dan teks gate/KESENJANGAN sering memuatnya - tanpa ini pipeline crash.
        (_docs / "status.json").write_text(json.dumps(_status, ensure_ascii=False, indent=1),
                                           encoding="utf-8")


def emit(kind: str, **data):
    """Catat satu event.

    kind: stage_start|stage_end|agent|tool|tool_denied|gate|gate_answer|
    quota|cost|model|export|error|info
    """
    if kind == "stage_start":
        _run_cost.pop(data.get("label"), None)
    if not _docs:
        return
    ev = {"t": time.time(), "kind": kind, **data}
    with (_docs / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def set_status(**kw):
    _status.update(kw)
    _save()


def add_cost(label: str, usd: float):
    """Tambahkan hanya selisih dari laporan biaya sebelumnya pada tahap yang sama.

    ResultMessage terbit sekali per tahap dan membawa total tahap, bukan
    tambahan. Kalau satu tahap melaporkan lebih dari sekali, menambahkan nilai
    penuh tiap kali akan menggandakan biaya - jadi yang ditambahkan selisihnya.
    """
    c = _status["cost"]
    delta = usd - _run_cost.get(label, 0.0)
    _run_cost[label] = usd
    if delta <= 0:
        return
    c[label] = round(c.get(label, 0) + delta, 4)
    c["total"] = round(sum(v for k, v in c.items() if k != "total"), 4)
    _save()


def set_quota(**kw):
    _status["quota"].update(kw)
    _save()


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def _tg_cfg():
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    return (tok, chat) if tok and chat else (None, None)


BATAS_PESAN = 3900          # batas Telegram 4096, disisakan ruang untuk entitas HTML


def esc_html(t) -> str:
    """Telegram HTML hanya mengenal beberapa tag; sisanya harus di-escape."""
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def form(judul: str, baris: list[tuple[str, object]], catatan: str = "") -> str:
    """Pesan berbentuk formulir: judul tebal, lalu label dan nilai yang lurus.

    Label dipanjangkan dengan spasi tipis supaya kolom nilainya sejajar di HP,
    dan seluruh bagian nilai memakai <code> supaya lebarnya tetap.
    """
    isi = [x for x in baris if x[1] not in (None, "", [])]
    lebar = max((len(k) for k, _ in isi), default=0)
    teks = f"<b>{esc_html(judul)}</b>\n"
    if isi:
        teks += "<code>" + "\n".join(
            f"{esc_html(k.ljust(lebar))} : {esc_html(v)}" for k, v in isi) + "</code>"
    if catatan:
        teks += ("\n\n" if isi else "\n") + esc_html(catatan)
    return teks


# Tag yang dikenal Telegram. Pemotongan di tengah salah satunya membuat
# seluruh pesan ditolak, bukan sekadar kehilangan format.
_TAG_HTML = ("b", "strong", "i", "em", "u", "s", "code", "pre", "a")


def potong_html_aman(teks: str, batas: int) -> str:
    """Potong ke `batas` tanpa meninggalkan tag atau entitas yang terbelah.

    Jaring pengaman, bukan jalur utama: pemanggil seharusnya sudah menghitung
    muatannya. Kalau perhitungan itu meleset, lebih baik pesannya kehilangan
    ekor daripada hilang sama sekali.
    """
    if len(teks) <= batas:
        return teks

    def _rapikan(sampai: int) -> tuple[str, str]:
        potong = teks[:sampai]
        # Buang tag atau entitas yang terbelah di ujung.
        for buka, tutup in (("<", ">"), ("&", ";")):
            i = potong.rfind(buka)
            if i != -1 and potong.find(tutup, i) == -1:
                potong = potong[:i]
        terbuka = []
        for m in re.finditer(r"<(/?)(\w+)[^>]*>", potong):
            nama = m.group(2).lower()
            if nama not in _TAG_HTML:
                continue
            if m.group(1):
                if terbuka and terbuka[-1] == nama:
                    terbuka.pop()
            else:
                terbuka.append(nama)
        return potong, "".join(f"</{x}>" for x in reversed(terbuka))

    # Tag penutup ikut dihitung: tanpa ini hasilnya bisa melewati batas yang
    # justru sedang dijaga. Dua putaran cukup - memotong lebih pendek hanya
    # bisa mengurangi tag yang terbuka, tidak pernah menambah.
    sampai = batas
    for _ in range(2):
        potong, tutup = _rapikan(sampai)
        if len(potong) + len(tutup) <= batas:
            return potong + tutup
        sampai = batas - len(tutup)
    potong, tutup = _rapikan(sampai)
    return (potong + tutup)[:batas]


def tg_send(text: str, tombol: list | None = None, html: bool = False,
            paksa_balas: str | None = None):
    """Kirim pesan. `tombol` = [[(label, data), ...], ...] menjadi tombol inline.

    Tombol dipakai untuk gate: menekan tombol jauh lebih kecil kemungkinan
    salahnya daripada mengetik 'y' di ponsel, dan teks yang salah ketik akan
    diperlakukan sebagai masukan revisi.

    `paksa_balas` membuka kolom isian Telegram dengan contoh di dalamnya. Itu
    padanan terdekat dari kotak masukan di dashboard; tanpa ini, menulis masukan
    hanya disebut di satu baris petunjuk dan mudah terlewat.
    """
    tok, chat = _tg_cfg()
    if not tok:
        return
    kirim = {"chat_id": chat,
             "text": potong_html_aman(text, BATAS_PESAN) if html
                     else text[:BATAS_PESAN]}
    if html:
        kirim["parse_mode"] = "HTML"
    if tombol:
        kirim["reply_markup"] = json.dumps({"inline_keyboard": [
            [{"text": t, "callback_data": d} for t, d in baris] for baris in tombol]})
    elif paksa_balas is not None:
        # input_field_placeholder dibatasi 64 karakter oleh Telegram.
        kirim["reply_markup"] = json.dumps({
            "force_reply": True, "input_field_placeholder": paksa_balas[:64]})
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    try:
        urllib.request.urlopen(url, urllib.parse.urlencode(kirim).encode(), timeout=10)
        return
    except Exception as e:
        # Telegram menaruh sebab sesungguhnya di badan balasan; tanpa ini yang
        # tercatat hanya "Bad Request" dan penyebabnya harus ditebak.
        sebab = str(e)
        badan = getattr(e, "read", None)
        if badan:
            try:
                sebab = json.loads(badan()).get("description", sebab)
            except Exception:
                pass
        print(f"  (telegram gagal: {sebab})")

    if not html:
        return
    # Pesan gate yang gagal berarti pertanyaan tidak terlihat sementara pipeline
    # tetap menunggu jawabannya. Lebih baik kehilangan format daripada itu.
    polos = re.sub(r"<[^>]+>", "", text)
    polos = (polos.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    kirim.pop("parse_mode", None)
    kirim["text"] = polos[:BATAS_PESAN]
    try:
        urllib.request.urlopen(url, urllib.parse.urlencode(kirim).encode(), timeout=10)
        print("  (dikirim ulang tanpa format)")
    except Exception as e:  # notifikasi tidak boleh menjatuhkan pipeline
        print(f"  (telegram gagal lagi, tanpa format: {e})")


# Kata-kata pilihan gate sengaja sama dengan dashboard (kartuGate di
# dashboard.py). Pemilik proyek menjawab gate yang sama dari dua tempat; kalau
# pilihannya berbeda nama, ia harus menerjemahkan sendiri mana yang mana.
GATE_SETUJU = "Setuju, lanjutkan"
GATE_BERHENTI = "Berhenti"
GATE_MASUKAN = "Tulis masukan"
GATE_CONTOH = "Contoh: point 3 terlalu panjang, pangkas bagian sejarahnya."


MAKS_BAGIAN = 8             # rem supaya satu gate tidak membanjiri chat


def _muat(teks: str, batas: int) -> int:
    """Panjang awalan terpanjang yang setelah di-escape masih muat `batas`.

    Dicari pada teks MENTAH, bukan hasil escape: memotong hasil escape bisa
    membelah entitas seperti `&amp;` di tengah, dan Telegram menolak pesannya.
    """
    if len(esc_html(teks)) <= batas:
        return len(teks)
    rendah, tinggi = 0, len(teks)
    while rendah < tinggi:
        tengah = (rendah + tinggi + 1) // 2
        if len(esc_html(teks[:tengah])) <= batas:
            rendah = tengah
        else:
            tinggi = tengah - 1
    return max(rendah, 1)


def bagi_pesan(teks: str, batas: int) -> list[str]:
    """Bagi teks menjadi beberapa pesan yang masing-masing muat `batas`.

    Dipotong di pergantian baris supaya blok tidak terbelah di tengah kalimat.
    Baris tunggal yang lebih panjang dari satu pesan tetap dipotong paksa.
    """
    potongan: list[str] = []
    kini = ""
    for baris in teks.splitlines(keepends=True):
        while len(esc_html(baris)) > batas:
            if kini:
                potongan.append(kini)
                kini = ""
            pas = _muat(baris, batas)
            potongan.append(baris[:pas])
            baris = baris[pas:]
        if kini and len(esc_html(kini + baris)) > batas:
            potongan.append(kini)
            kini = baris
        else:
            kini += baris
    if kini.strip():
        potongan.append(kini)
    if not potongan:
        return [teks]
    if len(potongan) > MAKS_BAGIAN:
        # Bagian awal dan bagian AKHIR yang dipertahankan: KESENJANGAN —
        # hal yang harus diputuskan manusia — selalu ada di ujung pertanyaan.
        buang = len(potongan) - MAKS_BAGIAN + 1
        potongan = (potongan[:MAKS_BAGIAN - 2]
                    + [f"[ {buang} bagian di tengah dilewati — teks penuhnya ada "
                       f"di berkas yang dilampirkan di atas, dan di dashboard ]"]
                    + potongan[-1:])
    return potongan


def minta_masukan(label: str = ""):
    """Buka kolom isian masukan di Telegram, setara kotak teks di dashboard."""
    judul = f"✍ Masukan untuk {label}" if label else "✍ Masukan"
    tg_send(form(judul, [], "Balas pesan ini dengan masukan revisi, atau dengan "
                            "jawaban atas pertanyaan di gate.\n\n" + GATE_CONTOH),
            html=True, paksa_balas=GATE_CONTOH)


def _tg_jawab_tombol(cb_id: str, teks: str):
    """Hentikan animasi tunggu di tombol yang baru ditekan."""
    tok, _ = _tg_cfg()
    if not tok:
        return
    try:
        data = urllib.parse.urlencode({"callback_query_id": cb_id, "text": teks[:180]}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/answerCallbackQuery",
                               data, timeout=10)
    except Exception:
        pass


def tg_doc(path, caption: str = ""):
    """Kirim satu berkas ke Telegram sebagai dokumen.

    Berkas .md dikirim dengan nama .txt supaya Telegram menampilkan isinya
    langsung di aplikasi; kalau tetap .md, Telegram memaksa unduh dan minta
    aplikasi lain. Sama seperti tg_send, kegagalan tidak menjatuhkan pipeline.
    """
    tok, chat = _tg_cfg()
    path = Path(path)
    if not tok or not path.exists():
        return
    size = path.stat().st_size
    if size == 0:
        return
    if size > 45 * 1024 * 1024:          # batas Telegram 50 MB
        tg_send(f"{path.name} terlalu besar ({size // 1024} KB). Buka lewat dashboard.")
        return

    name = path.stem + ".txt" if path.suffix == ".md" else path.name
    b = uuid.uuid4().hex
    crlf = chr(13) + chr(10)

    def field(n, v):
        return (f"--{b}{crlf}Content-Disposition: form-data; "
                f'name="{n}"{crlf}{crlf}{v}{crlf}').encode()

    body = field("chat_id", chat)
    if caption:
        body += field("caption", caption[:1000])
    body += (f"--{b}{crlf}Content-Disposition: form-data; "
             f'name="document"; filename="{name}"{crlf}'
             f"Content-Type: text/plain; charset=utf-8{crlf}{crlf}").encode()
    body += path.read_bytes() + f"{crlf}--{b}--{crlf}".encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendDocument", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        urllib.request.urlopen(req, timeout=60)
    except Exception as e:
        print(f"  (telegram gagal kirim {name}: {e})")


def _tg_poll() -> str | None:
    """Ambil satu pesan teks baru dari chat yang dikonfigurasi. None kalau tidak ada."""
    global _tg_offset
    tok, chat = _tg_cfg()
    if not tok:
        return None
    try:
        url = f"https://api.telegram.org/bot{tok}/getUpdates?timeout=0&offset={_tg_offset}"
        with urllib.request.urlopen(url, timeout=10) as r:
            for u in json.load(r).get("result", []):
                _tg_offset = u["update_id"] + 1
                cb = u.get("callback_query") or {}
                if cb and str((cb.get("message") or {}).get("chat", {}).get("id")) == str(chat):
                    data = (cb.get("data") or "").strip()
                    if data == "masukan":
                        # Bukan jawaban: ini permintaan membuka kolom isian.
                        # Gate tetap menunggu sampai teksnya benar-benar dikirim.
                        _tg_jawab_tombol(cb.get("id", ""), "Tulis masukanmu")
                        minta_masukan((_status.get("gate") or {}).get("label") or "")
                        continue
                    _tg_jawab_tombol(cb.get("id", ""),
                                     "Disetujui" if data == "y" else "Dihentikan")
                    if data in ("y", "q"):
                        return data
                    continue
                m = u.get("message") or {}
                if str(m.get("chat", {}).get("id")) == str(chat) and m.get("text"):
                    return m["text"].strip()
    except Exception:
        pass
    return None


def _balas_perintah(teks: str) -> bool:
    """Perintah yang masuk SAAT gate terbuka dijawab di tempat, bukan dipakai
    sebagai jawaban gate.

    Tanpa ini, mengetik `/status` saat pipeline menunggu gate akan diterima
    sebagai masukan revisi — satu putaran revisi yang mahal dan tidak diminta.
    """
    if not teks.startswith("/"):
        return False
    cmd = teks.split()[0].lower().lstrip("/")
    g = _status.get("gate") or {}
    if cmd in ("status", "s"):
        c = _status.get("cost") or {}
        kuota = _status.get("quota") or {}
        tg_send(form("Keadaan pipeline", [
            ("Proyek", _status.get("project") or "-"),
            ("Tahap", _status.get("current") or "-"),
            ("Point", (f"{_status.get('point')} · {_status.get('point_judul', '')}"[:60]
                       if _status.get("point") else None)),
            ("Gate", g.get("label")),
            ("Biaya", f"${(c.get('total') or 0):.2f}"),
            ("Kuota", (f"{kuota.get('type', '')} — {kuota.get('status')}"
                       if kuota.get("status") else None)),
        ], "Pipeline menunggu jawabanmu. Balas: y / q / teks masukan."
           if g.get("label") else "Tidak ada gate yang menunggu."), html=True)
    elif cmd in ("help", "bantuan", "start"):
        tg_send(form("Menjawab gate", [
            (f"✅ {GATE_SETUJU}", "tombol, atau ketik y"),
            (f"⏹ {GATE_BERHENTI}", "tombol, atau ketik q"),
            (f"✍ {GATE_MASUKAN}", "tombol, atau langsung ketik masukannya"),
            ("/status", "keadaan pipeline"),
        ], "Pilihannya sama persis dengan yang ada di dashboard.\n\n"
           "Perintah lain (/daftar, /lanjut, /stop) hanya berfungsi saat tidak ada "
           "pipeline berjalan."), html=True)
    else:
        tg_send(f"Perintah '{cmd}' tidak berlaku saat gate terbuka, dan TIDAK dipakai "
                f"sebagai jawaban. Balas y / q / teks masukan, atau /status.")
    return True


def tg_drain():
    """Buang pesan lama supaya jawaban gate tidak diambil dari pesan sebelum pipeline jalan."""
    while _tg_poll() is not None:
        pass


# ---------------------------------------------------------------------------
# Gate: tunggu jawaban dari terminal, dashboard, ATAU Telegram
# ---------------------------------------------------------------------------
_stdin_q: queue.Queue = queue.Queue()
_stdin_started = False

# Dashboard berjalan di proses lain dan tidak bisa menulis ke stdin pipeline yang
# sudah terlepas, jadi kanalnya berupa satu berkas di docs/. Dibaca lalu langsung
# dihapus, supaya jawaban yang sama tidak terpakai dua kali di gate berikutnya.
BERKAS_JAWAB = "GATE_JAWAB.txt"


def _stdin_reader():
    while True:
        try:
            _stdin_q.put(input())
        except EOFError:
            return


def _baca_jawaban_berkas() -> str | None:
    if not _docs:
        return None
    p = _docs / BERKAS_JAWAB
    if not p.exists():
        return None
    try:
        teks = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None          # dashboard mungkin sedang menulisnya; coba lagi nanti
    p.unlink(missing_ok=True)
    return teks or None


def buang_jawaban_tertinggal():
    """Buang jawaban dashboard yang tertinggal dari gate sebelumnya.

    Tanpa ini, jawaban yang ditulis saat pipeline sudah lewat gate akan langsung
    dipakai gate berikutnya tanpa dibaca manusia.
    """
    if _docs:
        (_docs / BERKAS_JAWAB).unlink(missing_ok=True)


async def ask(question: str, label: str, files: list | None = None) -> str:
    global _stdin_started
    print("\n" + "=" * 70 + f"\n{question}\n"
          "Ketik 'y' untuk setuju, 'q' untuk berhenti, atau tulis masukan revisi.\n"
          + "=" * 70)
    emit("gate", label=label, question=question)
    set_status(gate={"label": label, "question": question, "since": time.time()})
    tg_drain()
    buang_jawaban_tertinggal()
    # Lampirkan dokumennya dulu, pertanyaan belakangan, supaya pertanyaan
    # jadi pesan terakhir dan paling terlihat di chat.
    for f in files or []:
        tg_doc(f, f"{label}: {Path(f).name} - baca dulu, lalu jawab pertanyaan di bawah.")
    c = _status.get("cost") or {}
    baris = [
        ("Proyek", _status.get("project") or "-"),
        ("Tahap", _status.get("current") or "-"),
        ("Point", (f"{_status.get('point')} · {_status.get('point_judul', '')}"[:60]
                   if _status.get("point") else None)),
        ("Biaya", f"${(c.get('total') or 0):.2f}"),
    ]
    ekor = ("\n\n<b>Pilihan Anda</b>\n"
            f"<code>✅ {GATE_SETUJU}</code> — lanjut ke tahap berikutnya\n"
            f"<code>⏹ {GATE_BERHENTI}</code> — pipeline berhenti, dokumen tetap tersimpan\n"
            f"<code>✍ {GATE_MASUKAN}</code> — dokumen direvisi sesuai masukanmu\n"
            "\n<i>Masukan bisa juga langsung: balas pesan ini dengan teks.</i>")
    kepala = form(f"⏸ Menunggu keputusan — {label}", baris)
    # Batas Telegram berlaku per pesan, bukan per gate. Pertanyaan panjang
    # karena itu dikirim berurutan alih-alih dipotong: memotongnya berarti
    # pemilik proyek memutuskan tanpa melihat sebagian bahannya.
    # Pesan TERAKHIR memuat kepala dan ekor sekaligus, jadi ruang untuk
    # keduanya harus disisihkan - bukan yang terpanjang saja. Dengan max(),
    # pesan terakhir bisa 100+ karakter melewati batas, terpotong di tengah
    # <code> pada ekor, dan ditolak Telegram dengan 400. Akibatnya pertanyaan
    # gate tidak pernah sampai dan pipeline menunggu jawaban yang tak terlihat.
    jatah = BATAS_PESAN - len(kepala) - len(ekor) - 60
    bagian = bagi_pesan(question, jatah)
    n = len(bagian)
    for i, isi in enumerate(bagian, 1):
        awal = kepala if i == 1 else f"<b>({label} — lanjutan {i}/{n})</b>"
        # Tombol hanya di pesan terakhir: ia yang paling bawah di chat, dan
        # menjawab dari potongan tengah berarti menjawab sebelum selesai membaca.
        tg_send(awal + "\n\n" + esc_html(isi).strip() + (ekor if i == n else ""),
                tombol=[[("✅ " + GATE_SETUJU, "y"), ("⏹ " + GATE_BERHENTI, "q")],
                        [("✍ " + GATE_MASUKAN, "masukan")]] if i == n else None,
                html=True)

    if not _stdin_started:
        threading.Thread(target=_stdin_reader, daemon=True).start()
        _stdin_started = True

    while True:
        # Tiga kanal, diperiksa berurutan tiap putaran. Yang tiba lebih dulu
        # dipakai; sisanya tidak pernah ikut terbaca karena ask() langsung pulang.
        try:
            ans = _stdin_q.get_nowait().strip()
            src = "terminal"
        except queue.Empty:
            ans, src = _baca_jawaban_berkas(), "dashboard"
            if not ans:
                ans, src = _tg_poll(), "telegram"
                # Perintah (/status, /help) dijawab di tempat. Tanpa ini, mengetik
                # /status saat gate terbuka diterima sebagai MASUKAN REVISI.
                if ans and _balas_perintah(ans):
                    ans = None
        if ans:
            print(f"> [{src}] {ans}")
            emit("gate_answer", label=label, answer=ans, source=src)
            set_status(gate=None)
            if src == "telegram":
                tg_send(form("✅ Jawaban diterima", [
                    ("Gate", label),
                    ("Jawaban", "setuju, lanjutkan" if ans.lower() == "y"
                     else "berhenti" if ans.lower() == "q" else ans[:120]),
                ]), html=True)
            return ans
        await asyncio.sleep(2)
