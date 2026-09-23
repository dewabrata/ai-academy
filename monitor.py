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


def tg_send(text: str, tombol: list | None = None, html: bool = False):
    """Kirim pesan. `tombol` = [[(label, data), ...], ...] menjadi tombol inline.

    Tombol dipakai untuk gate: menekan tombol jauh lebih kecil kemungkinan
    salahnya daripada mengetik 'y' di ponsel, dan teks yang salah ketik akan
    diperlakukan sebagai masukan revisi.
    """
    tok, chat = _tg_cfg()
    if not tok:
        return
    kirim = {"chat_id": chat, "text": text[:3900]}
    if html:
        kirim["parse_mode"] = "HTML"
    if tombol:
        kirim["reply_markup"] = json.dumps({"inline_keyboard": [
            [{"text": t, "callback_data": d} for t, d in baris] for baris in tombol]})
    try:
        data = urllib.parse.urlencode(kirim).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=10)
    except Exception as e:  # notifikasi tidak boleh menjatuhkan pipeline
        print(f"  (telegram gagal: {e})")


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
        tg_send("Pipeline sedang menunggu jawaban gate. Yang dikenali sekarang:\n"
                "  y = setuju dan lanjutkan\n"
                "  q = berhenti (pekerjaan tetap tersimpan)\n"
                "  teks lain = masukan revisi\n"
                "  /status = keadaan pipeline\n\n"
                "Perintah lain (/daftar, /lanjut, /stop) hanya berfungsi saat tidak ada "
                "pipeline berjalan.")
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
    tg_send(form(f"⏸ Menunggu keputusan — {label}", [
        ("Proyek", _status.get("project") or "-"),
        ("Tahap", _status.get("current") or "-"),
        ("Point", (f"{_status.get('point')} · {_status.get('point_judul', '')}"[:60]
                   if _status.get("point") else None)),
        ("Biaya", f"${(c.get('total') or 0):.2f}"),
    ], question[:2600]) + "\n\n<i>Tekan tombol, atau balas teks untuk memberi masukan "
       "revisi.</i>",
        tombol=[[("✅ Setuju, lanjutkan", "y"), ("⏹ Berhenti", "q")]], html=True)

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
