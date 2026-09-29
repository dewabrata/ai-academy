"""Pusat kendali AI Academy: menjalankan academy.py dari dashboard atau Telegram.

Dipakai dashboard.py. Tiga aturan yang menjaga supaya tidak kacau:

1. Satu pipeline per proyek. academy.py menulis `.locks/<proyek>.lock` berisi
   PID-nya dan menghapusnya saat selesai; di sini kuncinya dibaca, bukan ditebak.
2. Kunci dari proses yang sudah mati dilaporkan sebagai kedaluwarsa, tidak
   diklaim diam-diam — academy.py yang memutuskan mengambilnya.
3. Telegram hanya didengarkan saat TIDAK ada pipeline berjalan. Antrean
   getUpdates milik bot cuma satu dan offset-nya bersama — kalau dua proses ikut
   membaca, jawaban gate bisa tertelan di sini dan hilang.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

import monitor          # dipakai untuk monitor.form(): satu gaya pesan Telegram

ROOT = Path(__file__).parent
WS = ROOT / "workspace"
LOCKS = ROOT / ".locks"
ARSIP = ROOT / "workspace" / ".arsip"
TAHAP = ["kurikulum", "blueprint", "produksi", "akhir"]
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")

# Format silabus yang boleh diunggah. Sama dengan yang dibaca silabus.py —
# menerima lebih banyak di sini hanya memindahkan kegagalan ke tengah pipeline.
SILABUS_EXT = {".md", ".txt", ".docx", ".pdf"}
SILABUS_MAKS = 20 * 1024 * 1024


# ---------------------------------------------------------------------------
# Status pipeline
# ---------------------------------------------------------------------------
def _proses_hidup(pid) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True, timeout=15).stdout
            return str(pid) in out
        except Exception:
            return True
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError):
        return True


def running(project: str) -> dict | None:
    """Info pipeline proyek ini, atau None. Kunci basi ditandai `basi: True`
    supaya dashboard bisa menampilkannya apa adanya."""
    lp = LOCKS / f"{project}.lock"
    if not lp.exists():
        return None
    try:
        info = json.loads(lp.read_text(encoding="utf-8"))
    except Exception:
        return {"pid": None, "project": project, "action": "?", "started": 0, "basi": True}
    info["basi"] = not _proses_hidup(info.get("pid"))
    return info


def running_any() -> list[dict]:
    if not LOCKS.exists():
        return []
    out = []
    for lp in sorted(LOCKS.glob("*.lock")):
        info = running(lp.stem)
        if info and not info.get("basi"):
            out.append(info)
    return out


def stop(project: str) -> tuple[bool, str]:
    info = running(project)
    if not info:
        return False, f"Tidak ada pipeline berjalan untuk '{project}'."
    pid = info.get("pid")
    if info.get("basi") or not pid:
        (LOCKS / f"{project}.lock").unlink(missing_ok=True)
        return True, "Kunci sudah tidak hidup, dihapus."
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=20)
        else:
            os.kill(int(pid), 15)
    except Exception as e:
        return False, f"Gagal menghentikan PID {pid}: {e}"
    (LOCKS / f"{project}.lock").unlink(missing_ok=True)
    return True, f"Pipeline (PID {pid}) dihentikan. Dokumen tetap tersimpan."


# ---------------------------------------------------------------------------
# Daftar proyek
# ---------------------------------------------------------------------------
def daftar_proyek() -> list[dict]:
    if not WS.exists():
        return []
    out = []
    for d in sorted(WS.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not (d / "docs").is_dir():
            continue
        st = _status(d.name)
        r = running(d.name)
        out.append({
            "nama": d.name,
            "tahap": (d / "docs" / "STATE.txt").read_text(encoding="utf-8").strip()
                     if (d / "docs" / "STATE.txt").exists() else "baru",
            "pertemuan": len(list((d / "materi").glob("pertemuan-*"))) if (d / "materi").exists() else 0,
            "biaya": (st.get("cost") or {}).get("total", 0),
            "gate": (st.get("gate") or {}).get("label"),
            "berjalan": bool(r and not r.get("basi")),
            "diubah": d.stat().st_mtime,
        })
    return out


def _status(project: str) -> dict:
    p = WS / project / "docs" / "status.json"
    if not p.exists():
        return {}
    data = p.read_bytes()
    for enc in ("utf-8", "cp1252"):
        try:
            return json.loads(data.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {}


def default_project() -> str | None:
    d = daftar_proyek()
    return d[0]["nama"] if d else None


# ---------------------------------------------------------------------------
# Menjalankan academy.py
# ---------------------------------------------------------------------------
def simpan_klien(project: str, data: bytes) -> tuple[bool, str]:
    """Simpan konteks klien sebagai docs/KLIEN.md. Semua peran membacanya kalau
    ada, jadi tidak perlu diteruskan lewat argumen pipeline."""
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek tidak valid."
    if not data:
        return False, "Berkas konteks klien kosong."
    if len(data) > 2 * 1024 * 1024:
        return False, "Konteks klien terlalu besar (batas 2 MB)."
    d = WS / project / "docs"
    d.mkdir(parents=True, exist_ok=True)
    (d / "KLIEN.md").write_bytes(data)
    return True, "Konteks klien tersimpan."


def start(project: str, action: str, text: str = "", pilot: int | None = None,
          opsi_proyek: dict | None = None, env_tambahan: dict | None = None) -> tuple[bool, str]:
    """action: baru | lanjut | resume. text: path/teks silabus, atau nama tahap.

    `opsi_proyek` ditulis ke docs/OPSI.json sebelum pipeline jalan, supaya
    pipeline membacanya sendiri dan perilakunya sama walau dijalankan dari
    terminal."""
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek hanya boleh huruf, angka, - dan _."
    r = running(project)
    if r and not r.get("basi"):
        return False, (f"Pipeline untuk '{project}' masih berjalan (PID {r.get('pid')}). "
                       f"Hentikan dulu atau tunggu selesai.")

    cmd = [sys.executable, "-u", "academy.py"]

    if action == "slide":
        if not (WS / project).exists():
            return False, f"Proyek '{project}' tidak ada di workspace/."
        nomor = (text or "semua").strip() or "semua"
        if nomor not in ("semua", "all") and not nomor.isdigit():
            return False, "Nomor pertemuan harus angka, atau 'semua'."
        cmd += ["--project", project, "--slide", nomor]
        _spawn(cmd, project, env_tambahan)
        return True, (f"Membuat slide untuk "
                      f"{'semua pertemuan' if nomor in ('semua', 'all') else 'pertemuan ' + nomor}.")

    if action == "bahan":
        if not (WS / project).exists():
            return False, f"Proyek '{project}' tidak ada di workspace/."
        nomor = (text or "semua").strip() or "semua"
        if nomor not in ("semua", "all") and not nomor.isdigit():
            return False, "Nomor pertemuan harus angka, atau 'semua'."
        cmd += ["--project", project, "--bahan", nomor]
        _spawn(cmd, project, env_tambahan)
        return True, (f"Membangun berkas kerja peserta untuk "
                      f"{'semua pertemuan' if nomor in ('semua', 'all') else 'pertemuan ' + nomor}. "
                      f"Point dan handbook tidak disentuh.")

    if action == "baru":
        if (WS / project / "docs" / "STATE.txt").exists():
            return False, f"Proyek '{project}' sudah pernah dijalankan. Pakai nama lain."
        sumber = _silabus_tersimpan(project) or (text or "").strip()
        if not sumber:
            return False, "Silabusnya belum ada. Unggah berkas atau tempel teksnya."
        cmd += [str(sumber), "--project", project]
    else:
        if not (WS / project).exists():
            return False, f"Proyek '{project}' tidak ada di workspace/."
        cmd += ["--project", project]
        if action == "resume":
            if text not in TAHAP:
                return False, f"Tahap harus salah satu dari: {', '.join(TAHAP)}."
            cmd += ["--resume", text]
        elif action != "lanjut":
            return False, f"Aksi '{action}' tidak dikenal."

    if pilot:
        cmd += ["--pilot", str(int(pilot))]

    if opsi_proyek:
        import opsi as opsi_mod
        opsi_mod.tulis(WS / project, opsi_proyek)

    _spawn(cmd, project, env_tambahan)
    return True, f"Dijalankan: {' '.join(cmd[2:])}"


def _spawn(cmd: list, project: str, env_tambahan: dict | None = None):
    """Jalankan academy.py terlepas dari dashboard, keluaran ke docs/pipeline.log."""
    log = WS / project / "docs" / "pipeline.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    f = log.open("a", encoding="utf-8")
    f.write(f"\n\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} :: {' '.join(cmd[2:])} =====\n")
    f.flush()
    # CREATE_NEW_PROCESS_GROUP / start_new_session supaya pipeline tidak ikut mati
    # kalau dashboard-nya ditutup.
    kw = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
          else {"start_new_session": True})
    # .env dibaca ULANG di sini, bukan sekadar diwarisi: dashboard bisa berjalan
    # berjam-jam, dan setelan yang diubah sesudahnya harus ikut ke pipeline yang
    # baru dijalankan. Tanpa ini, nilai lama dari saat dashboard start menang.
    load_dotenv(ROOT / ".env", override=True)
    # env_tambahan (mis. preset mutu maksimal) menang atas .env.
    env = {**os.environ, **{k: str(v) for k, v in (env_tambahan or {}).items()}}
    subprocess.Popen(cmd, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, env=env, **kw)


# ---------------------------------------------------------------------------
# Gate dari dashboard
# ---------------------------------------------------------------------------
def gate_tertunda(project: str) -> dict | None:
    return _status(project).get("gate")


def jawab_gate(project: str, jawaban: str) -> tuple[bool, str]:
    """Tulis jawaban gate ke docs/GATE_JAWAB.txt; monitor.ask yang membacanya.

    Dashboard tidak bisa menulis ke stdin pipeline yang sudah terlepas, jadi
    kanalnya berupa berkas. monitor.ask menghapusnya setelah terbaca.
    """
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek tidak valid."
    jawaban = (jawaban or "").strip()
    if not jawaban:
        return False, "Jawaban kosong."
    if not gate_tertunda(project):
        return False, "Tidak ada gate yang menunggu jawaban sekarang."
    docs = WS / project / "docs"
    if not docs.exists():
        return False, f"Proyek '{project}' tidak ada."
    (docs / "GATE_JAWAB.txt").write_text(jawaban, encoding="utf-8")
    return True, f"Jawaban dikirim: {jawaban[:120]}"


# ---------------------------------------------------------------------------
# Unggah silabus sebelum pipeline jalan
# ---------------------------------------------------------------------------
def dir_sumber(project: str) -> Path:
    return WS / project / "sumber"


def _silabus_tersimpan(project: str) -> Path | None:
    d = dir_sumber(project)
    if not d.exists():
        return None
    # silabus.txt adalah hasil normalisasi milik pipeline, bukan unggahan.
    for f in sorted(d.iterdir()):
        if f.is_file() and f.name != "silabus.txt" and f.suffix.lower() in SILABUS_EXT:
            return f
    return None


def siapkan_proyek(project: str) -> tuple[bool, str]:
    """Buat folder proyek TANPA menjalankan pipeline, supaya silabus bisa
    diunggah dulu. Pipeline dimulai belakangan lewat aksi 'baru'."""
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek hanya boleh huruf, angka, - dan _."
    if (WS / project / "docs" / "STATE.txt").exists():
        return False, f"Proyek '{project}' sudah pernah dijalankan. Pakai nama lain."
    for sub in ("docs", "materi", "sumber"):
        (WS / project / sub).mkdir(parents=True, exist_ok=True)
    return True, f"Proyek '{project}' siap. Unggah silabus, lalu mulai pipeline."


def simpan_silabus(project: str, nama: str, data: bytes) -> tuple[bool, str]:
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek tidak valid."
    # Path(...).name membuang direktori, jadi "../../.env" tidak bisa keluar folder.
    nama = Path(nama or "").name
    if not nama or nama.startswith("."):
        return False, "Nama berkas tidak valid."
    ext = Path(nama).suffix.lower()
    if ext not in SILABUS_EXT:
        return False, (f"Format '{ext or 'tanpa ekstensi'}' tidak didukung. "
                       f"Boleh: {', '.join(sorted(SILABUS_EXT))}")
    if not data:
        return False, "Berkas kosong."
    if len(data) > SILABUS_MAKS:
        return False, f"Berkas terlalu besar ({len(data) // 1024} KB, batas 20 MB)."
    if nama == "silabus.txt":
        return False, "Nama 'silabus.txt' dipakai pipeline. Ganti namanya."
    d = dir_sumber(project)
    d.mkdir(parents=True, exist_ok=True)
    (d / nama).write_bytes(data)
    return True, f"'{nama}' tersimpan sebagai silabus ({len(data) // 1024 or 1} KB)."


def daftar_silabus(project: str) -> list:
    d = dir_sumber(project)
    if not SAFE_NAME.match(project or "") or not d.exists():
        return []
    return sorted(({"nama": f.name, "byte": f.stat().st_size}
                   for f in d.iterdir() if f.is_file()), key=lambda x: x["nama"])


def hapus_silabus(project: str, nama: str) -> tuple[bool, str]:
    nama = Path(nama or "").name
    f = dir_sumber(project) / nama
    if not SAFE_NAME.match(project or "") or not nama or not f.is_file():
        return False, "Berkas tidak ditemukan."
    f.unlink()
    return True, f"'{nama}' dihapus."


# ---------------------------------------------------------------------------
# CRUD proyek
# ---------------------------------------------------------------------------
def _boleh_ubah(project: str) -> tuple[bool, str]:
    """Proyek hanya boleh dipindah/dihapus saat pipeline-nya tidak berjalan:
    memindahkan folder di bawah proses yang sedang menulis ke sana membuat
    materi separuh jadi tersebar di dua tempat."""
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek tidak valid."
    if not (WS / project / "docs").is_dir():
        return False, f"Proyek '{project}' tidak ada."
    r = running(project)
    if r and not r.get("basi"):
        return False, (f"Pipeline '{project}' masih berjalan (PID {r.get('pid')}). "
                       f"Hentikan dulu.")
    return True, ""


def arsipkan(project: str) -> tuple[bool, str]:
    """Pindahkan proyek ke workspace/.arsip/. Tidak menghapus apa pun: satu
    proyek bisa bernilai puluhan dolar biaya produksi, jadi 'hapus' di UI
    sebaiknya bisa dibatalkan."""
    ok, msg = _boleh_ubah(project)
    if not ok:
        return False, msg
    ARSIP.mkdir(parents=True, exist_ok=True)
    tujuan = ARSIP / f"{project}-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(str(WS / project), str(tujuan))
    return True, f"'{project}' diarsipkan ke {tujuan.name}. Bisa dipulihkan dari tab Arsip."


def daftar_arsip() -> list[dict]:
    if not ARSIP.exists():
        return []
    out = []
    for d in sorted(ARSIP.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        asal = d.name.rsplit("-", 2)[0]
        byte = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        out.append({"nama": d.name, "asal": asal, "diubah": d.stat().st_mtime,
                    "mb": round(byte / 1024 / 1024, 1),
                    "pertemuan": len(list((d / "materi").glob("pertemuan-*")))
                    if (d / "materi").exists() else 0})
    return out


def _arsip_path(nama: str) -> Path | None:
    nama = Path(nama or "").name
    p = (ARSIP / nama)
    try:
        p = p.resolve()
    except OSError:
        return None
    return p if ARSIP.exists() and ARSIP.resolve() in p.parents and p.is_dir() else None


def pulihkan(nama_arsip: str, nama_baru: str = "") -> tuple[bool, str]:
    p = _arsip_path(nama_arsip)
    if not p:
        return False, "Arsip tidak ditemukan."
    tujuan_nama = (nama_baru or p.name.rsplit("-", 2)[0]).strip()
    if not SAFE_NAME.match(tujuan_nama):
        return False, "Nama proyek hanya boleh huruf, angka, - dan _."
    if (WS / tujuan_nama).exists():
        return False, f"Nama '{tujuan_nama}' sudah dipakai. Beri nama lain."
    shutil.move(str(p), str(WS / tujuan_nama))
    return True, f"Dipulihkan sebagai '{tujuan_nama}'."


def hapus_arsip(nama_arsip: str, konfirmasi: str) -> tuple[bool, str]:
    """Hapus permanen. `konfirmasi` harus sama dengan nama arsipnya — satu
    klik tidak boleh cukup untuk menghapus materi yang sudah dibayar."""
    p = _arsip_path(nama_arsip)
    if not p:
        return False, "Arsip tidak ditemukan."
    if (konfirmasi or "").strip() != p.name:
        return False, "Ketik nama arsip persis untuk mengonfirmasi penghapusan."
    shutil.rmtree(p)
    return True, f"'{p.name}' dihapus permanen."


def ganti_nama(project: str, baru: str) -> tuple[bool, str]:
    ok, msg = _boleh_ubah(project)
    if not ok:
        return False, msg
    baru = (baru or "").strip()
    if not SAFE_NAME.match(baru):
        return False, "Nama baru hanya boleh huruf, angka, - dan _."
    if (WS / baru).exists():
        return False, f"Nama '{baru}' sudah dipakai."
    shutil.move(str(WS / project), str(WS / baru))
    (LOCKS / f"{project}.lock").unlink(missing_ok=True)
    return True, f"'{project}' diganti nama menjadi '{baru}'."


def duplikat(project: str, baru: str) -> tuple[bool, str]:
    """Proyek baru dengan silabus, konteks klien, dan opsi yang sama — TANPA
    materi. Yang disalin hanya masukan, bukan hasil produksi."""
    if not SAFE_NAME.match(project or "") or not (WS / project / "docs").is_dir():
        return False, f"Proyek '{project}' tidak ada."
    baru = (baru or "").strip()
    if not SAFE_NAME.match(baru):
        return False, "Nama baru hanya boleh huruf, angka, - dan _."
    if (WS / baru).exists():
        return False, f"Nama '{baru}' sudah dipakai."
    for sub in ("docs", "materi", "sumber"):
        (WS / baru / sub).mkdir(parents=True, exist_ok=True)
    asal = WS / project
    for f in (asal / "sumber").glob("*"):
        if f.is_file() and f.name != "silabus.txt":
            shutil.copyfile(f, WS / baru / "sumber" / f.name)
    for n in ("KLIEN.md", "OPSI.json"):
        if (asal / "docs" / n).is_file():
            shutil.copyfile(asal / "docs" / n, WS / baru / "docs" / n)
    return True, f"'{baru}' dibuat dari setelan '{project}'. Silabus dan opsi ikut disalin."


def hapus_klien(project: str) -> tuple[bool, str]:
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek tidak valid."
    f = WS / project / "docs" / "KLIEN.md"
    if not f.is_file():
        return False, "Konteks klien tidak ada."
    f.unlink()
    return True, "Konteks klien dihapus."


# ---------------------------------------------------------------------------
# Materi yang sudah jadi
# ---------------------------------------------------------------------------
def daftar_materi(project: str) -> list[dict]:
    m = WS / project / "materi"
    if not SAFE_NAME.match(project or "") or not m.exists():
        return []
    out = []
    for f in sorted(m.glob("pertemuan-*")):
        if not f.is_dir():
            continue
        berkas = sorted(x.name for x in f.iterdir() if x.is_file())
        point = [x for x in (f / "point").glob("point-[0-9][0-9].md")] if (f / "point").is_dir() else []
        out.append({
            "nama": f.name,
            "berkas": berkas,
            "point": len(point),
            "handbook": "HANDBOOK.md" in berkas,
            "slide": "SLIDE.md" in berkas,
            "latihan": "LATIHAN.md" in berkas and "KUNCI.md" in berkas,
            "praktik": "PRAKTIK.md" in berkas,
            "lab": (f / "lab" / "solusi").exists(),
            "bahan": (f / "bahan" / "jadi").exists(),
            # Berapa berkas yang ditampilkan isinya di point tetapi tidak
            # diserahkan. Angka inilah alasan tombol "Buat bahan kerja" muncul.
            "bahan_kurang": _bahan_kurang(f),
            "quiz": "QUIZ_AIKEN.txt" in berkas,
            "disetujui": (f / ".GATE_OK").exists(),
            "unduh": [x for x in ("HANDBOOK.docx", "SLIDE.pptx", "LATIHAN.docx", "KUNCI.docx",
                                  "PRAKTIK.docx", "QUIZ_AIKEN.txt", "PERTANYAAN.md", "PROSES.md")
                      if x in berkas],
        })
    return out


# ---------------------------------------------------------------------------
# Perintah lewat Telegram - HANYA saat tidak ada pipeline berjalan
# ---------------------------------------------------------------------------
_offset = 0

HELP = ("Perintah AI Academy (hanya saat tidak ada pipeline berjalan):\n"
        "/status - keadaan proyek aktif\n"
        "/proyek <nama> - pilih proyek yang dikendalikan\n"
        "/daftar - daftar semua proyek\n"
        "/lanjut - lanjutkan dari tahap terakhir\n"
        "/resume <tahap> - mulai dari tahap tertentu "
        "(kurikulum|blueprint|produksi|akhir)\n"
        "/stop - hentikan pipeline yang berjalan\n"
        "/kunci - bersihkan kunci yang ditinggalkan proses mati\n\n"
        "Saat pipeline berjalan, chat ini dipakai gate: balas y / q / teks masukan.\n"
        "Proyek baru dimulai dari dashboard atau terminal, karena silabusnya perlu "
        "diunggah dulu.")


def _tg(method: str, **params):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    if not tok:
        return None
    try:
        data = urllib.parse.urlencode(params).encode()
        with urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/{method}",
                                    data, timeout=20) as r:
            return json.load(r)
    except Exception:
        return None


def say(text: str, html: bool = False):
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not chat:
        return
    extra = {"parse_mode": "HTML"} if html else {}
    _tg("sendMessage", chat_id=chat, text=text[:3900], **extra)


def handle(text: str, project: str | None) -> tuple[str, str | None]:
    """Jalankan satu perintah. Mengembalikan (balasan, proyek terpilih)."""
    cmd, _, arg = text.strip().partition(" ")
    cmd, arg = cmd.lower().lstrip("/"), arg.strip()

    if cmd in ("start", "help", "bantuan"):
        return HELP, project
    if cmd == "daftar":
        d = daftar_proyek()
        if not d:
            return "Belum ada proyek di workspace/.", project
        return monitor.form("Daftar proyek", [
            (("▶ " if p["berjalan"] else "· ") + p["nama"][:24],
             f"{p['tahap']} · {p['pertemuan']} pertemuan · ${p['biaya']:.2f}")
            for p in d[:15]], "Pilih dengan /proyek <nama>."), project
    if cmd == "proyek":
        if not SAFE_NAME.match(arg or "") or not (WS / arg).exists():
            ada = ", ".join(p["nama"] for p in daftar_proyek()) or "(kosong)"
            return f"Proyek tidak ditemukan. Yang ada: {ada}", project

        return f"Proyek aktif sekarang: {arg}", arg

    project = project or default_project()
    if not project:
        return "Belum ada proyek di workspace/.", None

    if cmd == "status":
        st = _status(project)
        d = diagnosa(project)
        point = _status_point(project)
        siap = sum(1 for v in point.values() if v.get("status") == "siap")
        esk = [k for k, v in point.items() if v.get("status") == "eskalasi"]
        kuota = st.get("quota") or {}
        return monitor.form(f"Keadaan — {project}", [
            ("Tahap", f"{d['tahap']} · {d['keadaan']}"),
            ("Berjalan", d["sekarang"] or "-"),
            ("Pertemuan", f"{st.get('pertemuan_selesai', '-')} dari "
                          f"{st.get('pertemuan_total', '-')} disetujui"),
            ("Point", f"{siap} siap" + (f" · {len(esk)} eskalasi" if esk else "")),
            ("Eskalasi", ", ".join(esk[:6]) if esk else None),
            ("Skor", f"{st['skor_pemeriksaan']}%"
             if st.get("skor_pemeriksaan") is not None else None),
            ("Kuota", f"{kuota.get('type', '')} — {kuota.get('status')}"
             if kuota.get("status") else None),
            ("Biaya", f"${(st.get('cost') or {}).get('total', 0):.2f}"),
        ], d["saran"]), project
    if cmd == "kunci":
        return bersihkan_kunci(project)[1], project
    if cmd == "stop":
        return stop(project)[1], project
    if cmd in ("lanjut", "resume"):
        ok, msg = start(project, cmd, arg)
        return msg, project
    return f"Perintah '{cmd}' tidak dikenal.\n\n{HELP}", project


def _loop():
    global _offset
    project = None
    while True:
        try:
            # Pipeline berjalan = chat milik gate. Jangan sentuh antreannya.
            if running_any():
                time.sleep(3)
                continue
            res = _tg("getUpdates", timeout=0, offset=_offset)
            chat = os.getenv("TELEGRAM_CHAT_ID")
            for u in (res or {}).get("result", []):
                _offset = u["update_id"] + 1
                m = u.get("message") or {}
                t = (m.get("text") or "").strip()
                if not t or str(m.get("chat", {}).get("id")) != str(chat):
                    continue
                if not t.startswith("/"):
                    continue          # teks biasa bukan perintah: abaikan
                reply, project = handle(t, project)
                say(reply, html=True)
        except Exception:
            pass
        time.sleep(3)


def start_telegram_listener() -> bool:
    if not (os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")):
        return False
    threading.Thread(target=_loop, daemon=True).start()
    return True


# ---------------------------------------------------------------------------
# CLI pemulihan — dipakai saat dashboard mati atau pipeline tersangkut
# ---------------------------------------------------------------------------
BANTUAN = """Kendali AI Academy dari terminal (untuk pemulihan tanpa dashboard).

    python control.py status                 keadaan semua proyek
    python control.py status <proyek>        rincian satu proyek + saran langkah
    python control.py lanjut <proyek> [tahap]  jalankan lagi (tahap: kurikulum|blueprint|produksi|akhir)
    python control.py stop <proyek>          hentikan pipeline
    python control.py jawab <proyek> <teks>  jawab gate (y | q | teks masukan)
    python control.py kunci <proyek>         lihat/bersihkan kunci yang tertinggal
"""


def terapkan_setelan(project: str) -> tuple[bool, str]:
    """Hentikan pipeline lalu jalankan lagi, supaya setelan .env yang baru dipakai.

    Pipeline membaca `.env` saat ia MULAI. Mengubah API key, model, atau plafon
    di tengah jalan karena itu tidak berpengaruh sampai prosesnya dijalankan
    ulang. Tidak ada pekerjaan yang hilang: point yang sudah siap tidak ditulis
    ulang, dan gate yang sedang menunggu akan terbuka lagi.
    """
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek tidak valid."
    r = running(project)
    if r and not r.get("basi"):
        ok, msg = stop(project)
        if not ok:
            return False, msg
        for _ in range(20):                    # tunggu prosesnya benar-benar mati
            time.sleep(0.5)
            r = running(project)
            if not r or r.get("basi"):
                break
        else:
            return False, "Pipeline belum berhenti. Coba lagi sebentar lagi."
    ok, msg = start(project, "lanjut")
    return ok, ("Setelan baru diterapkan; pipeline dijalankan lagi dari titik terakhir."
                if ok else msg)


def bersihkan_kunci(project: str) -> tuple[bool, str]:
    """Hapus kunci yang ditinggalkan proses mati. Kunci milik proses HIDUP tidak
    pernah dihapus — dua pipeline menulis ke proyek yang sama jauh lebih buruk
    daripada satu kunci yang perlu dibersihkan manual."""
    if not SAFE_NAME.match(project or ""):
        return False, "Nama proyek tidak valid."
    r = running(project)
    if not r:
        return True, "Tidak ada kunci yang tertinggal."
    if not r.get("basi"):
        return False, (f"Kunci dipegang PID {r.get('pid')} yang masih hidup. "
                       f"Hentikan pipeline-nya dulu.")
    (LOCKS / f"{project}.lock").unlink(missing_ok=True)
    return True, "Kunci yang tertinggal dihapus. Pipeline bisa dijalankan lagi."


def diagnosa(project: str) -> dict:
    """Keadaan proyek + saran langkah, dalam bahasa manusia."""
    r = _ringkas(project)
    r["keadaan"] = ("menunggu-gate" if r["gate"] else "berjalan" if r["hidup"]
                    else "kunci-basi" if r["kunci_basi"] else "berhenti")
    r["saran"] = _saran(r)
    return r


def _status_point(project: str) -> dict:
    try:
        return json.loads((WS / project / "docs" / "PRODUKSI.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _bahan_kurang(f: Path) -> int:
    """Jumlah berkas yang ditampilkan isinya di point tetapi belum diserahkan."""
    try:
        import pemeriksa
    except Exception:
        return 0
    if not (f / "point").is_dir():
        return 0
    try:
        ada = pemeriksa.berkas_diserahkan(f)
        kurang = set()
        for bp in (f / "point").glob("point-[0-9][0-9].md"):
            for nama in pemeriksa.berkas_ditampilkan(bp.read_text(encoding="utf-8")):
                if nama not in ada and Path(nama).name not in ada:
                    kurang.add(nama)
        return len(kurang)
    except OSError:
        return 0


def _ringkas(project: str) -> dict:
    st = _status(project)
    r = running(project)
    docs = WS / project / "docs"
    gate = st.get("gate") or {}
    # Gate dianggap menunggu hanya kalau prosesnya hidup DAN gate itu dibuka
    # setelah tahap terakhir dimulai (lihat dashboard.gate_hidup).
    hidup = bool(r and not r.get("basi"))
    menunggu = (gate.get("label") if hidup and
                (gate.get("since") or 0) >= (st.get("current_since") or 0) else None)
    return {
        "nama": project, "hidup": hidup, "pid": (r or {}).get("pid"),
        "kunci_basi": bool(r and r.get("basi")),
        "tahap": (docs / "STATE.txt").read_text(encoding="utf-8").strip()
                 if (docs / "STATE.txt").exists() else "baru",
        "sekarang": st.get("current"), "gate": menunggu,
        "biaya": (st.get("cost") or {}).get("total", 0),
    }


def _saran(r: dict) -> str:
    if r["gate"]:
        return (f"Pipeline MENUNGGU jawaban Anda di gate {r['gate']}. Jawab di dashboard, "
                f"Telegram, atau:\n    python control.py jawab {r['nama']} y")
    if r["hidup"]:
        return f"Pipeline berjalan (PID {r['pid']}, tahap {r['sekarang']}). Tidak perlu apa-apa."
    if r["kunci_basi"]:
        return (f"Proses mati meninggalkan kunci. Pipeline berikutnya mengambilnya sendiri:\n"
                f"    python control.py lanjut {r['nama']}")
    if r["tahap"] in ("selesai", "baru"):
        return f"Proyek {r['tahap']}. Tidak ada yang perlu dipulihkan."
    return (f"Pipeline berhenti di tahap '{r['tahap']}'. Lanjutkan dari titik terakhir:\n"
            f"    python control.py lanjut {r['nama']}")


def _cli(argv: list[str]) -> int:
    perintah = (argv[0] if argv else "status").lower()
    nama = argv[1] if len(argv) > 1 else ""

    if perintah in ("-h", "--help", "bantuan"):
        print(BANTUAN)
        return 0

    if perintah == "status":
        daftar = [nama] if nama else [p["nama"] for p in daftar_proyek()]
        if not daftar:
            print("Belum ada proyek di workspace/.")
            return 0
        for n in daftar:
            r = _ringkas(n)
            tanda = ("MENUNGGU GATE" if r["gate"] else "berjalan" if r["hidup"]
                     else "kunci basi" if r["kunci_basi"] else "berhenti")
            print(f"{r['nama']:34s} {r['tahap']:10s} {tanda:14s} ${r['biaya']:.2f}"
                  + (f"  {r['sekarang']}" if r["hidup"] else ""))
            if nama:
                print("\n" + _saran(r))
        return 0

    if not nama:
        print(BANTUAN)
        return 2

    if perintah == "lanjut":
        tahap = argv[2] if len(argv) > 2 else ""
        ok, msg = start(nama, "resume" if tahap else "lanjut", tahap)
    elif perintah == "stop":
        ok, msg = stop(nama)
    elif perintah == "jawab":
        ok, msg = jawab_gate(nama, " ".join(argv[2:]))
    elif perintah == "kunci":
        lp = LOCKS / f"{nama}.lock"
        r = running(nama)
        if not r:
            ok, msg = True, "Tidak ada kunci."
        elif not r.get("basi"):
            ok, msg = False, (f"Kunci dipegang PID {r.get('pid')} yang MASIH HIDUP. "
                              f"Hentikan dulu: python control.py stop {nama}")
        else:
            lp.unlink(missing_ok=True)
            ok, msg = True, "Kunci yang tertinggal dihapus."
    else:
        print(BANTUAN)
        return 2

    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.exit(_cli(_sys.argv[1:]))
