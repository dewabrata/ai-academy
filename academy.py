"""AI Academy — pipeline produksi materi ajar dari silabus.

    silabus (.md/.txt/.docx/.pdf)
      -> KURIKULUM  : capaian belajar, level peserta, peta pertemuan    [gate]
      -> BLUEPRINT  : point per pertemuan (disalin dari silabus), jenis
                      tugas, alur sesi, logistik trainer                [gate]
      -> PRODUKSI   : pertemuan satu per satu, dan di dalamnya:
           per point, berurutan:
             WRITER -> REVIEWER + FACT-CHECKER (paralel) -> revisi, maks. 3 putaran
             (point 1 pertemuan pilot)                                  [gate PILOT]
           paket dari point final: SLIDE + TUGAS (paralel), HANDBOOK digabung,
           ekspor, pemeriksa, telaah paket, satu revisi                 [gate PERTEMUAN-n]
      -> AKHIR      : EDITOR menyeragamkan istilah, ekspor ulang, ringkasan

Pakai:
    python academy.py silabus.docx
    python academy.py "Pertemuan 1: pengenalan Python, 90 menit. Pertemuan 2: ..."
    python academy.py silabus.md --project pelatihan-python --pilot 3
    python academy.py silabus.docx --klien konteks/klien-dika.md
    python academy.py --project pelatihan-python --resume produksi
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    RateLimitEvent,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

import exporter
import monitor
import hooks_sdk
import opsi as opsi_mod
import pemeriksa
import rencana
import roles
import silabus as silabus_mod

# Konsol Windows default cp1252, sedangkan keluaran agent rutin memuat panah,
# em-dash, dan centang. Tanpa ini satu karakter saja menjatuhkan pipeline
# di tengah tahap lewat UnicodeEncodeError.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
# ANTHROPIC_API_KEY kosong = pakai login langganan Claude Code (OAuth).
if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ.pop("ANTHROPIC_API_KEY", None)

ROOT = Path(__file__).parent
WS = ROOT / "workspace"
LOCKS = ROOT / ".locks"

TAHAP = ["kurikulum", "blueprint", "produksi", "akhir"]


# ---------------------------------------------------------------------------
# Kunci satu-pipeline per proyek
# ---------------------------------------------------------------------------
def _proses_hidup(pid: int) -> bool:
    """Apakah PID itu masih jalan. Dipakai untuk membedakan pipeline yang
    benar-benar berjalan dari kunci yang tertinggal karena proses mati."""
    if not pid:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True, timeout=15).stdout
            return str(pid) in out
        except Exception:
            return True       # ragu-ragu: anggap hidup, jangan timpa pipeline orang
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def lock_path(project: str) -> Path:
    return LOCKS / f"{project}.lock"


def lock_acquire(project: str, action: str) -> tuple[bool, str]:
    """Umumkan pipeline ini sedang berjalan. False kalau sudah ada yang jalan."""
    LOCKS.mkdir(exist_ok=True)
    lp = lock_path(project)
    if lp.exists():
        try:
            info = json.loads(lp.read_text(encoding="utf-8"))
        except Exception:
            info = {}
        pid = info.get("pid")
        # Kunci milik proses ini sendiri bukan tabrakan — jangan menolak diri sendiri.
        if pid != os.getpid() and _proses_hidup(pid):
            sejak = datetime.fromtimestamp(info.get("started", 0)).strftime("%d %b %H:%M")
            return False, (f"Pipeline lain sedang berjalan untuk proyek '{project}' "
                           f"(PID {pid}, aksi {info.get('action')}, mulai {sejak}).")
        print(f">>> Kunci dari PID {pid} tidak lagi hidup — dianggap kedaluwarsa.")
    lp.write_text(json.dumps({"pid": os.getpid(), "project": project,
                              "action": action, "started": time.time()}), encoding="utf-8")
    return True, ""


def lock_release(project: str):
    lp = lock_path(project)
    try:
        if lp.exists() and json.loads(lp.read_text(encoding="utf-8")).get("pid") == os.getpid():
            lp.unlink()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Kegagalan tahap, sesi, kuota
# ---------------------------------------------------------------------------
class StageFailed(Exception):
    """Tahap gagal (kuota habis, error API, plafon biaya tercapai)."""


LAST_RATE_LIMIT: dict = {}


class Sessions:
    """session_id Claude Code per tahap, di docs/SESSIONS.json, supaya tahap yang
    terputus di tengah bisa dilanjutkan alih-alih dimulai dari nol."""

    def __init__(self, docs: Path):
        self.path = docs / "SESSIONS.json"
        self.data = monitor.baca_json(self.path)

    def get(self, label):
        return self.data.get(label)

    def set(self, label, sid):
        if sid and self.data.get(label) != sid:
            self.data[label] = sid
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def clear(self, label):
        if label in self.data:
            del self.data[label]
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


SESSIONS: Sessions | None = None
OPSI: dict = opsi_mod.bawaan()   # diisi pipeline() dari docs/OPSI.json
CLI_PATH: str | None = None     # diisi main() lewat cari_cli()


def note_rate_limit(ev: RateLimitEvent):
    info = ev.rate_limit_info
    LAST_RATE_LIMIT.update(status=info.status, resets_at=info.resets_at,
                           type=info.rate_limit_type, utilization=info.utilization)
    monitor.set_quota(status=info.status, type=info.rate_limit_type,
                      utilization=info.utilization, resets_at=info.resets_at)
    if info.status in ("allowed_warning", "rejected"):
        monitor.emit("quota", status=info.status, type=info.rate_limit_type,
                     utilization=info.utilization, resets_at=info.resets_at)
        pct = f"{info.utilization * 100:.0f}%" if info.utilization is not None else "?"
        print(f"  !! kuota {info.rate_limit_type}: {info.status} (terpakai {pct}), "
              f"reset {fmt_reset(info.resets_at)}")


def reset_epoch() -> float | None:
    r = LAST_RATE_LIMIT.get("resets_at")
    if not r:
        return None
    return r / 1000 if r > 1e12 else r      # server kadang kirim ms, kadang detik


def fmt_reset(r) -> str:
    if not r:
        return "(tidak diketahui)"
    e = r / 1000 if r > 1e12 else r
    return datetime.fromtimestamp(e).strftime("%d %b %H:%M")


# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
def budget(name: str, default: float) -> float | None:
    """Plafon satu tahap. `0` atau kosong berarti TANPA BATAS, bukan nol dolar:
    meneruskan 0 ke max_budget_usd membuat tahap berhenti seketika, dan itu
    kebalikan dari yang dimaksud pemilik proyek (design D3)."""
    try:
        v = float(os.getenv(f"BUDGET_{name}", default) or 0)
    except ValueError:
        v = float(default)
    return v if v > 0 else None


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default) or default))
    except ValueError:
        return default


def penyedia() -> str:
    """claude | openrouter | custom. USE_OPENROUTER=1 lama tetap dihormati."""
    p = os.getenv("AI_PROVIDER", "").strip().lower()
    if not p and os.getenv("USE_OPENROUTER") == "1":
        return "openrouter"
    return p or "claude"


def provider_env() -> dict:
    """Variabel lingkungan supaya Claude Code memanggil host lain.

    Claude Code hanya berbicara skema Anthropic (/v1/messages), jadi host kustom
    WAJIB melayani skema itu — endpoint yang cuma OpenAI tidak bisa dipakai.
    """
    p = penyedia()
    if p == "openrouter":
        return {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
                "ANTHROPIC_AUTH_TOKEN": os.environ["OPENROUTER_API_KEY"],
                "ANTHROPIC_API_KEY": ""}
    if p == "custom":
        base = os.environ["CUSTOM_BASE_URL"].strip().rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]      # Claude Code menambahkan /v1/messages sendiri
        model = os.environ["CUSTOM_MODEL"].strip()
        return {
            "ANTHROPIC_BASE_URL": base,
            "ANTHROPIC_AUTH_TOKEN": os.environ["CUSTOM_API_KEY"].strip(),
            "ANTHROPIC_API_KEY": "",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": os.getenv("CUSTOM_MODEL_OPUS", "").strip() or model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": os.getenv("CUSTOM_MODEL_SONNET", "").strip() or model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.getenv("CUSTOM_MODEL_HAIKU", "").strip() or model,
            "ANTHROPIC_SMALL_FAST_MODEL": os.getenv("CUSTOM_MODEL_HAIKU", "").strip() or model,
        }
    return {}


def cari_cli() -> str | None:
    """Path claude.exe native, atau None untuk memakai pencarian bawaan SDK.

    Di Windows, SDK menolak menjalankan shim npm `claude.cmd`: cmd.exe bisa
    mengeksekusi perintah yang diselipkan lewat argumen, dan tidak ada cara
    escaping yang andal. Paket npm yang sama sebenarnya membawa claude.exe
    native di bin/, jadi dicari di sana lebih dulu.
    """
    ditetapkan = os.getenv("CLAUDE_CLI_PATH", "").strip()
    if ditetapkan:
        if not Path(ditetapkan).is_file():
            raise SystemExit(f"CLAUDE_CLI_PATH menunjuk ke berkas yang tidak ada: {ditetapkan}")
        return ditetapkan
    if os.name != "nt":
        return None
    exe = shutil.which("claude.exe")
    if exe:
        return exe
    shim = shutil.which("claude")
    if shim:
        kandidat = (Path(shim).parent / "node_modules" / "@anthropic-ai"
                    / "claude-code" / "bin" / "claude.exe")
        if kandidat.is_file():
            return str(kandidat)
    return None


def akun_claude() -> str:
    """Akun Claude Code yang dipakai CLI di mesin ini.

    Ditampilkan supaya jelas kuota siapa yang terpakai: pipeline memakai login
    `claude` yang sama dengan editor, bukan akun terpisah.
    """
    try:
        d = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    akun = d.get("oauthAccount") or {}
    email, org = akun.get("emailAddress", ""), akun.get("organizationName", "")
    return f"{email}{f' · {org}' if org else ''}" if email else ""


def auth_mode() -> str:
    p = penyedia()
    if p == "openrouter":
        return "OpenRouter"
    if p == "custom":
        return f"host kustom {os.getenv('CUSTOM_BASE_URL')} (model {os.getenv('CUSTOM_MODEL')})"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "API key"
    akun = akun_claude()
    return f"langganan Claude (OAuth) — {akun}" if akun else "langganan Claude (OAuth)"


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------
async def gate(question: str, label: str = "GATE", files: list | None = None) -> str:
    """Tahan pipeline sampai ada keputusan manusia. 'q' menghentikan proses."""
    ans = await monitor.ask(question, label, files)
    if ans.lower() == "q":
        monitor.emit("info", msg="Dihentikan oleh pengguna")
        monitor.tg_send("⏹ Pipeline dihentikan oleh pengguna.")
        print("Dihentikan oleh pengguna. Dokumen yang sudah ada tetap tersimpan.")
        raise SystemExit(0)
    return ans


def biaya_total() -> float:
    return float((monitor._status.get("cost") or {}).get("total", 0) or 0)


def ringkas_biaya(label: str) -> str:
    c = monitor._status.get("cost") or {}
    return (f"Biaya tahap {label}: ${c.get(label, 0):.2f} · "
            f"kumulatif proyek: ${c.get('total', 0):.2f}")


async def cek_plafon_proyek():
    """Plafon total proyek. Bertanya, tidak memutus diam-diam: di titik ini
    sebagian materi biasanya sudah jadi dan menghentikannya tanpa bertanya
    justru membuang yang sudah dibayar."""
    plafon = budget("PROYEK", 0)
    if plafon is None or biaya_total() <= plafon:
        return
    await gate(f"Biaya proyek sudah ${biaya_total():.2f}, melewati plafon "
               f"BUDGET_PROYEK=${plafon:.2f}.\n"
               f"'y' = lanjutkan tanpa plafon, 'q' = berhenti.", label="PLAFON")
    os.environ["BUDGET_PROYEK"] = "0"      # sudah disetujui, jangan tanya lagi


# ---------------------------------------------------------------------------
# Eksekutor satu tahap
# ---------------------------------------------------------------------------
RESUME_NOTE = (
    "Kamu dimulai ulang setelah proses terputus (kuota habis / aplikasi mati). "
    "Beberapa langkah terakhirmu mungkin belum tersimpan. Cek dulu keadaan nyata "
    "di disk (berkas apa yang sudah ada dan isinya), lalu LANJUTKAN tugas ini — "
    "jangan mulai dari nol: "
)


async def run_stage(label: str, prompt: str, role: dict, cwd: Path, budget_usd: float,
                    wilayah: Path | None = None) -> str:
    """Satu tahap = satu query(). `wilayah` adalah folder tempat peran ini boleh
    menulis; ditegakkan oleh hook, bukan hanya diminta lewat prompt."""
    prev = SESSIONS.get(label) if SESSIONS else None
    model = OPSI.get("model") or role["model"]
    plafon = "tanpa batas" if budget_usd is None else f"${budget_usd}"
    if prev:
        print(f"\n### [{label}] RESUME sesi {prev[:8]}... — model={model} budget={plafon}")
        prompt = RESUME_NOTE + prompt
    else:
        print(f"\n### [{label}] mulai — model={model} budget={plafon}")
    monitor.emit("stage_start", label=label, model=model, resumed=bool(prev))
    # gate=None: kalau proses sebelumnya mati saat gate terbuka, status.json
    # masih menyimpan gate itu dan dashboard menampilkannya seolah menunggu
    # jawaban. Tahap yang mulai berarti tidak ada gate yang menunggu.
    monitor.set_status(current=label, current_since=time.time(), gate=None)
    monitor.tg_send(monitor.form(f"▶ {label} mulai" + (" · resume" if prev else ""), [
        ("Model", model), ("Plafon", plafon)]), html=True)

    opts = ClaudeAgentOptions(
        resume=prev,
        cwd=str(cwd),
        model=OPSI.get("model") or role["model"],
        system_prompt=role.get("system_prompt"),
        # tools = seluruh tool yang TERSEDIA; allowed_tools hanya persetujuan
        # otomatis. Tanpa tools=, peran tetap bisa memakai tool lain (design D7).
        tools=role["tools"],
        allowed_tools=role["tools"],
        disallowed_tools=roles.DENY_BASH,
        permission_mode="acceptEdits",
        setting_sources=[],
        max_budget_usd=budget_usd,
        env=provider_env(),
        cli_path=CLI_PATH,
        hooks=hooks_sdk.buat_hooks(label, cwd, wilayah),
    )
    final = ""
    err_kind = None
    async for msg in query(prompt=prompt, options=opts):
        if isinstance(msg, SystemMessage):
            if msg.subtype == "init":
                # Alias "opus" diterjemahkan CLI dan bisa berpindah saat Claude
                # Code diperbarui. Catat model SEBENARNYA supaya biaya dan mutu
                # tiap tahap bisa dirunut ke model yang nyata dipakai.
                asli = msg.data.get("model")
                if asli and asli != role.get("model"):
                    print(f"  [{label}] model: {role.get('model')} -> {asli}")
                monitor.emit("model", label=label, alias=role.get("model"), model=asli)
                if SESSIONS:
                    SESSIONS.set(label, msg.data.get("session_id"))
        elif isinstance(msg, RateLimitEvent):
            note_rate_limit(msg)
        elif isinstance(msg, AssistantMessage):
            if msg.error:
                err_kind = msg.error
                print(f"  [{label}] !! error dari API: {msg.error}")
            for b in msg.content:
                if isinstance(b, TextBlock) and b.text.strip():
                    print(f"  [{label}] {b.text.strip()[:300]}")
                    monitor.emit("agent", label=label, text=b.text.strip()[:600])
                elif isinstance(b, ToolUseBlock):
                    tgt = (b.input.get("file_path") or b.input.get("command")
                           or b.input.get("pattern") or "")
                    monitor.emit("tool", label=label, tool=b.name, target=str(tgt)[:160])
        elif isinstance(msg, ResultMessage):
            if SESSIONS:
                SESSIONS.set(label, msg.session_id)
            final = msg.result or ""
            print(f"### [{label}] selesai — turns={msg.num_turns} "
                  f"cost=${(msg.total_cost_usd or 0):.3f} subtype={msg.subtype}")
            monitor.add_cost(label, msg.total_cost_usd or 0)
            monitor.emit("stage_end", label=label, turns=msg.num_turns,
                         cost=msg.total_cost_usd, subtype=msg.subtype, ok=not msg.is_error)
            monitor.tg_send(monitor.form(
                f"{'✔' if not msg.is_error else '✖'} {label} selesai", [
                    ("Turn", msg.num_turns),
                    ("Biaya", f"${(msg.total_cost_usd or 0):.2f}"),
                    ("Kumulatif", f"${biaya_total():.2f}"),
                    ("Hasil", None if not msg.is_error else msg.subtype),
                ]), html=True)
            if msg.is_error or msg.subtype != "success":
                err_kind = err_kind or msg.subtype or "unknown"
                print(f"### [{label}] GAGAL: subtype={msg.subtype} "
                      f"http={msg.api_error_status} errors={msg.errors}")
    if err_kind:
        monitor.emit("error", label=label, error=err_kind)
        raise StageFailed(f"{label}: {err_kind}")
    if SESSIONS:
        SESSIONS.clear(label)      # tahap sukses -> sesi tidak perlu di-resume
    return final


# Kuota habis datang dengan beberapa wajah: event RateLimitEvent, subtype
# rate_limit, HTTP 429, dan teks CLI "You've hit your session limit". Yang
# terakhir sempat lolos dan membuat pipeline berhenti bertanya padahal
# seharusnya menunggu reset (kejadian 22 Sep 2026).
POLA_KUOTA = re.compile(r"rate.?limit|session limit|usage limit|quota|(?<!\d)429(?!\d)", re.I)


def kena_kuota(e: BaseException) -> bool:
    return bool(POLA_KUOTA.search(str(e))) or LAST_RATE_LIMIT.get("status") == "rejected"


# Jaringan putus (WiFi mati, DNS kacau, VPN pindah) mematikan tahap yang sedang
# jalan, padahal komputernya baik-baik saja. Ini beda dari kuota habis: tidak
# perlu menunggu berjam-jam, cukup menunggu jaringan kembali lalu mengulang
# tahap yang sama. Kejadian 23 Sep 2026: pipeline mati di menit ke-85 produksi.
POLA_JARINGAN = re.compile(
    r"ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT|ENETUNREACH|EHOSTUNREACH|"
    r"can'?t reach the api server|getaddrinfo|socket hang up|connection (error|refused|reset)|"
    r"network (error|is unreachable)|temporary failure in name resolution", re.I)


def kena_jaringan(e: BaseException) -> bool:
    return bool(POLA_JARINGAN.search(str(e)))


async def tunggu_jaringan(label: str, percobaan: int) -> bool:
    """Tidur sebentar lalu minta tahap diulang. True = coba lagi.

    Jeda naik bertahap (30 detik, 60, 120, ... maksimal 5 menit) supaya jaringan
    yang mati sebentar pulih cepat, sementara jaringan yang mati lama tidak
    dipukul terus-menerus.
    """
    maks = float(os.getenv("JARINGAN_TUNGGU_MENIT", 120) or 120)
    jeda = min(30 * (2 ** (percobaan - 1)), 300)
    if percobaan * jeda > maks * 60:
        print(f">>> Jaringan masih putus setelah {maks:.0f} menit mencoba. Menyerah; "
              f"lanjutkan nanti dengan --resume.")
        return False
    print(f">>> Jaringan tidak terjangkau. Menunggu {jeda} detik lalu mengulang {label} "
          f"(percobaan {percobaan}).")
    monitor.set_status(current=f"menunggu jaringan ({label})")
    monitor.emit("jaringan", label=label, percobaan=percobaan, jeda=jeda)
    if percobaan == 1:
        monitor.tg_send(monitor.form("🌐 Jaringan putus", [
            ("Tahap", label), ("Jeda", f"{jeda} detik"),
        ], "Pipeline menunggu jaringan kembali lalu mengulang tahap ini sendiri."), html=True)
    await asyncio.sleep(jeda)
    return True


async def wait_for_quota(label: str) -> bool:
    """Tunggu sampai kuota reset menurut server. True = ulangi tahap."""
    mode = os.getenv("QUOTA_WAIT", "auto")
    max_h = float(os.getenv("QUOTA_WAIT_MAX_HOURS", 6) or 6)
    reset = reset_epoch()
    secs = (reset - time.time() + 60) if reset else 0     # +1 menit jaga-jaga
    kind = LAST_RATE_LIMIT.get("type", "?")

    if secs <= 0:
        secs = 5 * 60
        print(">>> Kuota/rate limit tanpa info reset. Menunggu 5 menit lalu coba lagi.")
    else:
        print(f">>> Kuota {kind} habis. Reset menurut server: "
              f"{fmt_reset(LAST_RATE_LIMIT['resets_at'])} (~{secs / 3600:.1f} jam lagi).")

    if mode == "ask" or secs > max_h * 3600:
        ans = await gate(f"Tahap {label} berhenti karena kuota. "
                         f"'y' = tunggu sampai reset lalu ulang otomatis, "
                         f"'q' = berhenti (lanjutkan nanti dengan --resume).", label="KUOTA")
        if ans.lower() != "y":
            return False

    until = datetime.fromtimestamp(time.time() + secs).strftime("%d %b %H:%M")
    print(f">>> Tidur sampai {until} ...")
    monitor.set_status(current=f"menunggu kuota s/d {until}")
    monitor.tg_send(monitor.form("💤 Kuota habis — pipeline menunggu", [
        ("Jenis", kind), ("Tahap", label), ("Lanjut", until),
    ], "Tidak perlu tindakan; pipeline mengulang tahap ini sendiri setelah reset."),
        html=True)
    await asyncio.sleep(secs)
    return True


async def run_stage_retry(label, prompt, role, cwd, budget_usd, boleh_tanya=True, wilayah=None):
    """Bungkus run_stage: kuota habis -> tunggu lalu ulang; gagal lain -> tawarkan
    ulang dengan model setingkat lebih tinggi.

    boleh_tanya=False dipakai untuk tahap yang berjalan paralel: dua tahap yang
    sama-sama bertanya di gate akan berebut stdin dan jawaban bisa masuk ke
    tahap yang salah. Kegagalannya dilempar dan diputuskan pemanggilnya.
    """
    percobaan_jaringan = 0
    while True:
        try:
            return await run_stage(label, prompt, role, cwd, budget_usd, wilayah)
        except StageFailed as e:
            print(f"\n>>> {e}")
            if kena_jaringan(e):
                percobaan_jaringan += 1
                if await tunggu_jaringan(label, percobaan_jaringan):
                    continue
                raise
            percobaan_jaringan = 0
            is_quota = kena_kuota(e)
            if (not is_quota and SESSIONS and SESSIONS.get(label)
                    and "invalid_request" in str(e)):
                print(f">>> Sesi lama tidak bisa di-resume. Mulai sesi baru untuk {label}.")
                SESSIONS.clear(label)
                continue
            if is_quota:
                if boleh_tanya:
                    if await wait_for_quota(label):
                        continue
                raise
            if not boleh_tanya:
                raise
            # Gagal berulang sering berarti tahapnya terlalu berat untuk model
            # itu, bukan sekadar sial. Tawarkan naik satu tingkat.
            naik = roles.naik_model(role.get("model", ""))
            tawaran = (f"'y' = ulang dengan model {naik} (naik dari {role['model']})"
                       if naik else
                       f"'y' = ulang dengan model {role.get('model')} (sudah tertinggi)")
            ans = await gate(f"Tahap {label} gagal ({e}). {tawaran}, "
                             f"'q' = berhenti (lanjutkan nanti dengan --resume).",
                             label=f"GAGAL-{label}")
            if ans.lower() != "y":
                raise
            if naik:
                # Salin dict-nya: definisi peran di roles.py dipakai bersama tahap
                # lain, jangan sampai kenaikan ini bocor ke sana.
                role = {**role, "model": naik}
                print(f">>> {label} dinaikkan ke model {naik}.")
                monitor.emit("info", msg=f"{label} dinaikkan ke model {naik}")


def kesenjangan(teks: str) -> str:
    """Ambil blok KESENJANGAN dari laporan akhir sebuah peran.

    Keluhan peran tidak berguna kalau terkubur di dokumen puluhan kilobyte —
    ini menaikkannya ke pertanyaan gate, supaya dilihat saat memutuskan.
    """
    if not teks:
        return ""
    i = teks.upper().rfind("KESENJANGAN")
    if i < 0:
        return ""
    baris = [b.rstrip() for b in teks[i:].strip().splitlines()]
    isi = [b for b in baris[1:] if b.strip().startswith(("-", "*", "1", "2", "3", "4", "5"))]
    if not isi and "tidak ada" in baris[0].lower():
        return ""
    return "\n".join(isi[:5])


# ---------------------------------------------------------------------------
# Tahap dokumen dengan gate
# ---------------------------------------------------------------------------
async def doc_with_gate(label: str, doc: str, prompt: str, role: dict, ws: Path,
                        budget_usd: float, lampiran: list | None = None,
                        tambahan_gate: str = "", ringkas_fn=None, telaah_fn=None):
    """Tulis dokumen -> gate -> revisi sampai disetujui."""
    docs = ws / "docs"
    fb = docs / f"{doc}_FEEDBACK.md"
    # Penanda "dokumen sudah jadi, tinggal menunggu persetujuan". Kalau proses
    # mati tepat di gate, restart langsung ke gate — tahap tidak digenerate ulang.
    pending = docs / f".{doc}_PENDING_GATE"
    while True:
        if pending.exists() and (docs / f"{doc}.md").exists():
            print(f">>> {doc}.md sudah ada — langsung ke gate, tidak digenerate ulang.")
        else:
            pending.unlink(missing_ok=True)
            laporan = await run_stage_retry(label, prompt, role, ws, budget_usd,
                                            wilayah=docs)
            pending.write_text(laporan or "1", encoding="utf-8")

        # Telaah dokumen dijalankan SETELAH dokumen jadi dan SEBELUM gate, supaya
        # pemilik proyek memutuskan dengan temuan di tangan.
        hasil_telaah = await telaah_fn() if telaah_fn else ""

        gap = kesenjangan(pending.read_text(encoding="utf-8"))
        tanya = f"Review {docs / (doc + '.md')}. Setuju?"
        if tambahan_gate:
            tanya += f"\n\n{tambahan_gate}"
        if ringkas_fn:
            tanya += f"\n\n{ringkas_fn()}"
        if hasil_telaah:
            tanya += f"\n\n{hasil_telaah}"
        if gap:
            tanya += f"\n\nYang dikeluhkan {label}:\n{gap}"
        tanya += f"\n\n{ringkas_biaya(label)}"

        ans = await gate(tanya, label=label, files=(lampiran or []) + [docs / f"{doc}.md"])
        pending.unlink(missing_ok=True)
        if ans.lower() == "y":
            fb.unlink(missing_ok=True)
            return
        fb.write_text(ans, encoding="utf-8")
        print(f">>> Masukan disimpan ke {fb.name}, {label} mengerjakan revisi.")


async def telaah_blueprint(ws: Path) -> str:
    """Telaah blueprint sebelum dipakai memproduksi semua point.

    Blueprint dibaca setiap peran di setiap point, jadi satu kekurangan di sana
    berlipat sebanyak jumlah point — dan Writer tidak berwenang memperbaikinya.
    Penelaah hanya melaporkan; yang memutuskan tetap pemilik proyek di gate.
    """
    docs = ws / "docs"
    out = docs / "TELAAH_BLUEPRINT.md"
    out.unlink(missing_ok=True)
    try:
        await run_stage_retry("TELAAH-BLUEPRINT", (
            "Mode blueprint. Telaah docs/BLUEPRINT.md terhadap sumber/silabus.txt dan "
            "docs/KURIKULUM.md. Periksa kelengkapan konvensi, kesepadanan jatah menit "
            "dengan langkah 'Di kelas', pertentangan internal, batas antarpoint, dan "
            "kesetiaan daftar point pada silabus.\n"
            f"Tulis catatanmu ke {_rel(ws, out)} dengan format wajib. JANGAN mengubah "
            "docs/BLUEPRINT.md — kamu melaporkan, pemilik proyek yang memutuskan."
        ), roles.REVIEWER, ws, budget("BLUEPRINT_TELAAH", 2.0), boleh_tanya=False,
            wilayah=docs)
    except StageFailed as e:
        return f"Telaah blueprint gagal ({e}). Blueprint tetap bisa disetujui apa adanya."

    revisi = butir_catatan(out, "Revisi")
    tanya = butir_catatan(out, "Perlu dicek-ditanyakan")
    if not revisi and not tanya:
        return "Telaah blueprint: tidak ada temuan."
    baris = [f"Telaah blueprint ({len(revisi)} temuan, {len(tanya)} pertanyaan) — "
             f"lengkapnya di {_rel(ws, out)}:"]
    baris += [f"- {b[:200]}" for b in revisi[:6]]
    if len(revisi) > 6:
        baris.append(f"- ... dan {len(revisi) - 6} temuan lain")
    baris += [f"- (tanya) {b[:160]}" for b in tanya[:3]]
    return "\n".join(baris)


# ---------------------------------------------------------------------------
# Membaca blueprint
# ---------------------------------------------------------------------------
daftar_pertemuan = rencana.daftar_pertemuan


def ringkas_blueprint(ws: Path) -> str:
    """Yang dibaca Python dari blueprint, ditampilkan di gate Blueprint supaya
    salah salin point atau jenis tugas tertangkap sebelum produksi."""
    ps = daftar_pertemuan(ws)
    if not ps:
        return "!! Python tidak menemukan satu pun '## Pertemuan <n>' di blueprint."
    baris = ["Yang akan diproduksi (dibaca dari blueprint):"]
    for p in ps:
        baris.append(f"- Pertemuan {p['no']} — {p['judul'][:50]}: {len(p['point'])} point, "
                     f"tugas {'+'.join(sorted(p['jenis']))}")
        for pt in p["point"]:
            baris.append(f"    {pt['no']}. {pt['judul'][:70]}"
                         + (f"  ({', '.join(pt['capaian'])})" if pt["capaian"] else "  (!! tanpa capaian)"))
        if not p["point"]:
            baris.append("    !! tidak ada point — periksa bagian '### Point'")
    return "\n".join(baris)


# ---------------------------------------------------------------------------
# Lokasi dan status
# ---------------------------------------------------------------------------
def folder_pertemuan(ws: Path, no: int) -> Path:
    return ws / "materi" / f"pertemuan-{no:02d}"


def berkas_point(f: Path, k: int) -> Path:
    return f / "point" / f"point-{k:02d}.md"


def berkas_catatan(f: Path, k: int) -> Path:
    return f / "point" / f"point-{k:02d}.catatan.md"


def berkas_review(f: Path, k: int, r: int) -> Path:
    return f / "review" / f"point-{k:02d}-review-r{r}.md"


def berkas_fakta(f: Path, k: int, r: int) -> Path:
    return f / "review" / f"point-{k:02d}-fakta-r{r}.md"


def _rel(ws: Path, p: Path) -> str:
    return p.relative_to(ws).as_posix()


def _berkas_status(ws: Path) -> Path:
    # Di docs/, bukan di folder pertemuan: tidak ada peran produksi yang boleh
    # menulis ke docs/, jadi status loop tidak bisa tertimpa peran.
    return ws / "docs" / "PRODUKSI.json"


def status_semua(ws: Path) -> dict:
    return monitor.baca_json(_berkas_status(ws)) or {}


def status_point(ws: Path, no: int, k: int) -> dict:
    st = status_semua(ws).get(f"{no:02d}.{k:02d}") or {}
    return {"status": "proses", "ditulis": 0, "ditelaah": 0, "awal": 0, "riwayat": [], **st}


def simpan_status_point(ws: Path, no: int, k: int, st: dict):
    semua = status_semua(ws)
    semua[f"{no:02d}.{k:02d}"] = st
    _berkas_status(ws).write_text(json.dumps(semua, ensure_ascii=False, indent=1), encoding="utf-8")


STATUS_BARIS = re.compile(r"^\W*status\W*:\s*(.+?)\s*$", re.I | re.M)


def _status_akhir(p: Path) -> str:
    """Baris `Status:` terakhir di berkas telaah, huruf kecil, tanpa penanda."""
    if not p.exists():
        return ""
    semua = STATUS_BARIS.findall(p.read_text(encoding="utf-8"))
    return re.sub(r"[*_`]", "", semua[-1]).strip().lower() if semua else ""


def siap_review(p: Path) -> bool | None:
    s = _status_akhir(p)
    if "siap ditunjukkan" in s:
        return True
    if "perlu revisi" in s:
        return False
    return None           # tidak ada / tidak terbaca (design D2)


def siap_fakta(p: Path) -> bool | None:
    s = _status_akhir(p)
    if "tidak ada koreksi" in s:      # diperiksa lebih dulu: memuat "ada koreksi"
        return True
    if "ada koreksi" in s:
        return False
    return None


def skor_review(p: Path) -> dict:
    if not p.exists():
        return {}
    m = re.search(r"<!--\s*SKOR\s+(.*?)-->", p.read_text(encoding="utf-8"), re.S)
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d)", m.group(1))} if m else {}


JUDUL_CATATAN = re.compile(r"^\W*(revisi|perlu dicek-ditanyakan|sudah oke lanjut|status)\W*:", re.I)


def butir_catatan(p: Path, bagian: str) -> list[str]:
    """Butir di satu bagian catatan Reviewer (mis. 'Perlu dicek-ditanyakan')."""
    if not p.exists():
        return []
    hasil, di_dalam = [], False
    for baris in p.read_text(encoding="utf-8").splitlines():
        m = JUDUL_CATATAN.match(baris)
        if m:
            di_dalam = m.group(1).lower() == bagian.lower()
            continue
        b = baris.strip()
        if di_dalam and b.startswith(("-", "*")) and "tidak ada" not in b.lower()[:14]:
            hasil.append(b.lstrip("-* ").strip())
    return hasil


def pertanyaan_writer(p: Path) -> list[str]:
    if not p.exists():
        return []
    teks = p.read_text(encoding="utf-8")
    m = re.search(r"^##\s*Pertanyaan.*$", teks, re.I | re.M)
    if not m:
        return []
    sisa = teks[m.end():]
    akhir = re.search(r"^##\s", sisa, re.M)
    sisa = sisa[:akhir.start()] if akhir else sisa
    return [b.strip().lstrip("-* ").strip() for b in sisa.splitlines()
            if b.strip().startswith(("-", "*")) and "tidak ada" not in b.lower()[:14]]


# ---------------------------------------------------------------------------
# Prompt tugas per tahap
# ---------------------------------------------------------------------------
def rujukan_umum(ws: Path, p: dict) -> str:
    docs = ws / "docs"
    teks = (f"- docs/KURIKULUM.md (level peserta, prasyarat, capaian pertemuan {p['no']})\n"
            f"- docs/BLUEPRINT.md, bagian '## Konvensi lintas pertemuan' DAN "
            f"'## Pertemuan {p['no']}'\n"
            f"- docs/GLOSARIUM.md\n")
    if (docs / "KLIEN.md").exists():
        teks += "- docs/KLIEN.md — konteks dan aturan gaya khusus klien.\n"
    if (docs / "ACUAN_GAYA.md").exists():
        teks += ("- docs/ACUAN_GAYA.md — koreksi gaya dari pemilik proyek. MENGIKAT dan "
                 "menang atas preferensi di prompt-mu.\n")
    return teks


def berkas_konvensi(ws: Path, p: dict, k: int) -> list[Path]:
    """Catatan konvensi point-point sebelumnya di pertemuan ini, urut nomor."""
    f = folder_pertemuan(ws, p["no"])
    return [x for x in sorted((f / "point").glob("point-[0-9][0-9].konvensi.md"))
            if int(x.name.split("-")[1].split(".")[0]) < k]


def rujukan_sebelumnya(ws: Path, p: dict, k: int) -> str:
    f = folder_pertemuan(ws, p["no"])
    konv = berkas_konvensi(ws, p, k)
    awalan = ""
    if konv:
        awalan = (f"- {', '.join(_rel(ws, x) for x in konv[-6:])} — keputusan yang sudah "
                  f"diambil Writer point sebelumnya. Pakai nilai yang sama.\n")
    if k > 1:
        teks = (f"- {_rel(ws, berkas_point(f, k - 1))} — point sebelumnya. Baca UTUH: "
                f"studi kasus point ini melanjutkan dari sana.\n")
        if k > 2:
            teks += (f"- point 1–{k - 2} di {_rel(ws, f / 'point')}/ — baca judul dan "
                     f"subjudulnya saja (Grep '^#'), supaya tidak mengulang.\n")
        return awalan + teks
    # Point pertama: sambung ke point terakhir pertemuan sebelumnya, kalau ada.
    lalu = sorted(x for x in (ws / "materi").glob("pertemuan-*/point/point-[0-9][0-9].md")
                  if int(x.parent.parent.name.split("-")[1]) < p["no"])
    if lalu:
        return awalan + (f"- {_rel(ws, lalu[-1])} — point terakhir pertemuan sebelumnya. "
                         f"Baca untuk kesinambungan studi kasus antarpertemuan.\n")
    return awalan


def prompt_writer(ws: Path, p: dict, pt: dict, r: int, st: dict) -> str:
    f = folder_pertemuan(ws, p["no"])
    k = pt["no"]
    teks = (f"Kerjakan POINT {k} dari PERTEMUAN {p['no']} — \"{pt['judul']}\" "
            f"(capaian: {', '.join(pt['capaian']) or 'lihat blueprint'}).\n"
            f"Panjang target: {OPSI['point_halaman']} halaman.\n\n"
            f"Baca lebih dulu:\n{rujukan_umum(ws, p)}{rujukan_sebelumnya(ws, p, k)}\n"
            f"Tulis point ke {_rel(ws, berkas_point(f, k))}, asumsi dan pertanyaan ke "
            f"{_rel(ws, berkas_catatan(f, k))}, dan keputusan yang terpaksa kamu ambil "
            f"sendiri ke {_rel(ws, berkas_point(f, k)).replace('.md', '.konvensi.md')}, "
            f"dan jatah menit kelas ke "
            f"{_rel(ws, berkas_point(f, k)).replace('.md', '.kelas.md')}.\n\n")
    if r == st["awal"] + 1 and st.get("masukan"):
        teks += (f"Ini REVISI berdasarkan masukan pemilik proyek di {st['masukan']} "
                 f"(bagian terakhirnya). Terapkan masukan itu pada point yang sudah ada — "
                 f"sunting dengan Edit, jangan menulis ulang dari nol. Setelah itu point "
                 f"ditelaah ulang.\n")
    elif r > 1:
        teks += (f"Ini REVISI putaran {r}. Terapkan catatan Reviewer di "
                 f"{_rel(ws, berkas_review(f, k, r - 1))} dan koreksi Fact-Checker di "
                 f"{_rel(ws, berkas_fakta(f, k, r - 1))} pada point yang sudah ada — sunting "
                 f"dengan Edit, jangan menulis ulang dari nol.\n")
    else:
        teks += ("Tulis point baru. Kalau berkas point-nya sudah ada sebagian (sesi "
                 "sebelumnya terputus), lanjutkan dari situ, jangan mulai dari nol.\n")
    return teks


def prompt_bentuk(ws: Path, p: dict, pt: dict, langgar: list[str]) -> str:
    """Tugas perbaikan bentuk: mekanis, sempit, tidak memakai putaran telaah."""
    f = folder_pertemuan(ws, p["no"])
    k = pt["no"]
    return (f"Perbaiki BENTUK {_rel(ws, berkas_point(f, k))}. Pemeriksa otomatis "
            f"menemukan pelanggaran kontrak keterbacaan berikut:\n\n"
            + "\n".join(f"- {x}" for x in langgar)
            + "\n\nSunting dengan Edit, dan perbaiki hanya hal di atas. Jangan "
              "mengubah isi, contoh, angka, atau klaim apa pun, dan jangan "
              "memangkas materi - yang berubah hanya bentuknya. Aturan "
              "lengkapnya ada di bagian \"Kalimat dan paragraf\", \"Blok kode\", "
              "\"Istilah\", \"Tanpa rujukan ke bagian lain\", dan \"Informasi "
              "trainer bukan bacaan peserta\" di prompt peranmu.")


def prompt_reviewer_point(ws: Path, p: dict, pt: dict, r: int) -> str:
    f = folder_pertemuan(ws, p["no"])
    k = pt["no"]
    teks = (f"Mode point. Telaah {_rel(ws, berkas_point(f, k))} — point {k} pertemuan "
            f"{p['no']}: \"{pt['judul']}\" (capaian: {', '.join(pt['capaian']) or 'lihat blueprint'}), "
            f"putaran {r}.\n\nRujukan:\n{rujukan_umum(ws, p)}{rujukan_sebelumnya(ws, p, k)}")
    lama = berkas_review(f, k, r - 1)
    if r > 1 and lama.exists():
        teks += (f"\nCatatanmu putaran sebelumnya: {_rel(ws, lama)}. Periksa dulu apakah "
                 f"setiap butir Revisi-nya sudah dikerjakan.\n")
    fakta_lama = berkas_fakta(f, k, r - 1)
    if r > 1 and fakta_lama.exists():
        teks += (f"Hasil Fact-Checker putaran sebelumnya: {_rel(ws, fakta_lama)}. Klaim yang "
                 f"dinyatakan Benar di sana memang sudah tidak bertanda [CEK-FAKTA] — itu "
                 f"benar, jangan minta penandanya dipasang lagi.\n")
    teks += f"\nTulis catatanmu ke {_rel(ws, berkas_review(f, k, r))} dengan format wajib."
    return teks


def prompt_fakta(ws: Path, p: dict, pt: dict, r: int) -> str:
    f = folder_pertemuan(ws, p["no"])
    k = pt["no"]
    teks = f"Verifikasi klaim di {_rel(ws, berkas_point(f, k))} — point {k} pertemuan {p['no']}, putaran {r}.\n"
    if (ws / "docs" / "KLIEN.md").exists():
        teks += "Konteks klien: docs/KLIEN.md.\n"
    lama = berkas_fakta(f, k, r - 1)
    if r > 1 and lama.exists():
        teks += f"Hasil verifikasimu putaran sebelumnya: {_rel(ws, lama)}.\n"
    teks += f"\nTulis hasil verifikasi ke {_rel(ws, berkas_fakta(f, k, r))} dengan format wajib."
    return teks


# ---------------------------------------------------------------------------
# Loop satu point: Writer -> Reviewer + Fact-Checker -> revisi
# ---------------------------------------------------------------------------
async def _paralel_dengan_ulang(tugas: list[tuple], ws: Path, wilayah: Path, label_gate: str):
    """Jalankan tahap paralel; yang gagal ditawarkan untuk diulang lewat gate.

    boleh_tanya=False karena dua tahap paralel yang sama-sama bertanya akan
    berebut stdin. Kegagalan dikumpulkan lalu ditanyakan sekali.
    """
    percobaan_jaringan = 0
    while tugas:
        hasil = await asyncio.gather(*[
            run_stage_retry(label, prompt, role, ws, biaya, boleh_tanya=False, wilayah=wilayah)
            for label, prompt, role, biaya in tugas
        ], return_exceptions=True)
        gagal = []
        for t, h in zip(tugas, hasil):
            if isinstance(h, SystemExit):
                raise h
            if isinstance(h, BaseException):
                gagal.append((t, h))
            else:
                gap = kesenjangan(h)
                if gap:
                    monitor.emit("info", msg=f"{t[0]} KESENJANGAN", detail=gap[:400])
        if not gagal:
            return
        # Semua gagal karena jaringan = masalah bersama, bukan tahapnya. Tunggu
        # lalu ulang yang gagal saja, tanpa mengganggu pemilik proyek.
        if all(kena_jaringan(e) for _, e in gagal):
            percobaan_jaringan += 1
            if await tunggu_jaringan(gagal[0][0][0], percobaan_jaringan):
                tugas = [t for t, _ in gagal]
                continue
        if any(kena_kuota(e) for _, e in gagal):
            if await wait_for_quota(gagal[0][0][0]):
                tugas = [t for t, _ in gagal]
                continue
        await gate("Tahap gagal:\n" + "\n".join(f"- {t[0]}: {e}" for t, e in gagal)
                   + "\n\n'y' = ulangi yang gagal, 'q' = berhenti (lanjutkan nanti dengan --resume).",
                   label=label_gate)
        tugas = [t for t, _ in gagal]


# Perbaikan bentuk otomatis per point. Dua kali cukup: putaran pertama
# memperbaiki hampir semuanya, dan yang tersisa setelah dua kali biasanya butuh
# penilaian - itu wilayah Reviewer, bukan pemeriksa.
BENTUK_MAKS_PERBAIKAN = 2


async def produksi_point(ws: Path, p: dict, pt: dict) -> str:
    """Tuntaskan satu point. Mengembalikan 'siap' atau 'eskalasi'.

    Status disimpan setelah tiap langkah (ditulis / ditelaah per putaran),
    sehingga --resume melanjutkan tepat dari langkah yang terputus.
    """
    no, k = p["no"], pt["no"]
    f = folder_pertemuan(ws, no)
    kode = f"{no:02d}.{k:02d}"
    st = status_point(ws, no, k)
    if st["status"] in ("siap", "eskalasi"):
        return st["status"]
    (f / "point").mkdir(parents=True, exist_ok=True)
    (f / "review").mkdir(parents=True, exist_ok=True)
    maks = OPSI["point_maks_putaran"]
    monitor.set_status(point=f"{no}.{k}", point_judul=pt["judul"][:80])

    while True:
        r = st["ditelaah"] + 1
        if st["ditulis"] < r:
            print(f"\n>>> Point {no}.{k} — \"{pt['judul'][:60]}\", putaran {r}: menulis.")
            await run_stage_retry(f"WRITER-{kode}-r{r}", prompt_writer(ws, p, pt, r, st),
                                  roles.WRITER, ws, budget("POINT_WRITER", 4.0),
                                  wilayah=f / "point")
            if not berkas_point(f, k).exists():
                raise StageFailed(f"WRITER-{kode}: {berkas_point(f, k).name} tidak ditulis")
            st["ditulis"] = r
            st.pop("masukan", None)
            simpan_status_point(ws, no, k, st)

        # Bentuk diperiksa mesin sebelum Reviewer dipanggil: pelanggarannya
        # mekanis, jadi menyerahkannya ke Reviewer hanya membakar token dan
        # memakan jatah putaran untuk hal yang tidak butuh penilaian.
        for percobaan in range(1, BENTUK_MAKS_PERBAIKAN + 1):
            langgar = pemeriksa.bentuk_berkas_point(berkas_point(f, k))
            if not langgar:
                break
            print(f">>> Point {no}.{k}: bentuk belum sesuai "
                  f"({len(langgar)} jenis), perbaikan {percobaan}.")
            await run_stage_retry(f"BENTUK-{kode}-r{r}-{percobaan}",
                                  prompt_bentuk(ws, p, pt, langgar),
                                  roles.WRITER, ws, budget("POINT_BENTUK", 1.0),
                                  wilayah=f / "point")
        else:
            sisa = pemeriksa.bentuk_berkas_point(berkas_point(f, k))
            if sisa:
                print(f">>> Point {no}.{k}: bentuk masih dilanggar setelah "
                      f"{BENTUK_MAKS_PERBAIKAN} perbaikan, diteruskan ke Reviewer.")

        rev, fak = berkas_review(f, k, r), berkas_fakta(f, k, r)
        tugas = []
        # Berkas telaah yang sudah ada dan statusnya terbaca tidak diulang: itu
        # sisa sesi yang terputus setelah telaah selesai.
        if siap_review(rev) is None:
            tugas.append((f"REVIEWER-{kode}-r{r}", prompt_reviewer_point(ws, p, pt, r),
                          roles.REVIEWER, budget("POINT_REVIEW", 1.5)))
        if siap_fakta(fak) is None:
            tugas.append((f"FAKTA-{kode}-r{r}", prompt_fakta(ws, p, pt, r),
                          roles.FAKTA, budget("POINT_FAKTA", 1.5)))
        if tugas:
            print(f">>> Point {no}.{k}, putaran {r}: telaah Reviewer + Fact-Checker.")
            await _paralel_dengan_ulang(tugas, ws, f / "review", f"TELAAH-GAGAL-{kode}")

        ok_r, ok_f = siap_review(rev), siap_fakta(fak)
        st["ditelaah"] = r
        st["riwayat"].append({"r": r, "review": ok_r, "fakta": ok_f, "skor": skor_review(rev),
                              "revisi": len(butir_catatan(rev, "Revisi"))})
        hasil = None
        if ok_r and ok_f:
            hasil = "siap"
        elif r - st["awal"] >= maks:
            hasil = "eskalasi"
        if hasil:
            st["status"] = hasil
        simpan_status_point(ws, no, k, st)
        ket = (f"review {'siap' if ok_r else 'perlu revisi' if ok_r is False else '?'}, "
               f"fakta {'bersih' if ok_f else 'ada koreksi' if ok_f is False else '?'}")
        print(f">>> Point {no}.{k}, putaran {r}: {ket}" + (f" → {hasil.upper()}" if hasil else ""))
        monitor.emit("point", pertemuan=no, point=k, putaran=r, review=ok_r, fakta=ok_f,
                     status=hasil or "proses", skor=skor_review(rev))
        if hasil == "eskalasi":
            monitor.tg_send(monitor.form("⚠ Point dieskalasi", [
                ("Point", f"{no}.{k}"),
                ("Judul", pt["judul"][:50]),
                ("Putaran", f"{maks} (batas)"),
            ], f"Catatan terakhir dibawa ke gate pertemuan {no}. Produksi lanjut ke "
               f"point berikutnya."), html=True)
        if hasil:
            return hasil


def mulai_siklus_baru(ws: Path, no: int, k: int, masukan: str | None, sudah_ditulis: bool):
    """Buka siklus loop baru untuk point yang sudah selesai (setelah koreksi
    pilot atau masukan gate). Batas putaran dihitung ulang dari siklus ini."""
    st = status_point(ws, no, k)
    st.update(status="proses", awal=st["ditelaah"])
    st["ditulis"] = st["ditelaah"] + 1 if sudah_ditulis else st["ditelaah"]
    if masukan:
        st["masukan"] = masukan
    simpan_status_point(ws, no, k, st)


# ---------------------------------------------------------------------------
# Pilot di point pertama
# ---------------------------------------------------------------------------
def tambah_acuan_gaya(ws: Path, teks: str):
    acuan = ws / "docs" / "ACUAN_GAYA.md"
    lama = acuan.read_text(encoding="utf-8") if acuan.exists() else ""
    acuan.write_text(
        (lama + "\n" if lama else
         "# Acuan gaya\n\nKoreksi dari pemilik proyek. Berlaku untuk SEMUA point dan "
         "pertemuan, dan menang atas preferensi di prompt peran.\n\n")
        + f"## Masukan {datetime.now():%d %b %H:%M}\n{teks}\n", encoding="utf-8")


async def gate_pilot(ws: Path, p: dict, pt: dict):
    tanda = ws / "docs" / ".PILOT_OK"
    if tanda.exists():
        return
    f = folder_pertemuan(ws, p["no"])
    k = pt["no"]
    while True:
        st = status_point(ws, p["no"], k)
        r = st["ditelaah"]
        rev = berkas_review(f, k, r)
        tanya_r = butir_catatan(rev, "Perlu dicek-ditanyakan") + pertanyaan_writer(berkas_catatan(f, k))
        biaya = sum(v for kk, v in (monitor._status.get("cost") or {}).items()
                    if kk.startswith((f"WRITER-{p['no']:02d}.{k:02d}", f"REVIEWER-{p['no']:02d}.{k:02d}",
                                      f"FAKTA-{p['no']:02d}.{k:02d}")))
        tanya = (
            f"PILOT — point {k} pertemuan {p['no']}: \"{pt['judul']}\"\n"
            f"Berkas: {_rel(ws, berkas_point(f, k))}\n"
            f"Status loop: {st['status']} setelah {r} putaran"
            + (f" (skor tersembunyi terakhir: {st['riwayat'][-1]['skor']})" if st["riwayat"] else "") + "\n"
            + (("Pertanyaan yang terkumpul:\n" + "\n".join(f"- {q}" for q in tanya_r[:8]) + "\n")
               if tanya_r else "")
            + f"Biaya point ini: ${biaya:.2f}\n\n"
            "Periksa gaya, kedalaman, dan nadanya SEBELUM point berikutnya ditulis.\n"
            "'y' = setuju dan lanjutkan, teks = koreksi gaya (disimpan ke docs/ACUAN_GAYA.md, "
            "berlaku untuk SEMUA point, lalu point ini direvisi), 'q' = berhenti.")
        ans = await gate(tanya, label="PILOT",
                         files=[x for x in (berkas_point(f, k), berkas_catatan(f, k), rev) if x.exists()])
        if ans.lower() == "y":
            tanda.write_text(datetime.now().isoformat(), encoding="utf-8")
            return
        tambah_acuan_gaya(ws, ans)
        print(">>> Koreksi gaya disimpan ke ACUAN_GAYA.md; point pilot direvisi.")
        mulai_siklus_baru(ws, p["no"], k, "docs/ACUAN_GAYA.md", sudah_ditulis=False)
        await produksi_point(ws, p, pt)


# ---------------------------------------------------------------------------
# Paket pertemuan: slide, tugas, handbook, pemeriksa, telaah paket
# ---------------------------------------------------------------------------
def prompt_paket(ws: Path, p: dict, peran: str) -> str:
    f = folder_pertemuan(ws, p["no"])
    rel_f = _rel(ws, f)
    teks = (f"Kerjakan PERTEMUAN {p['no']} — {p['judul']}.\n\n"
            f"Sumber isimu: seluruh point final di {rel_f}/point/point-NN.md "
            f"({len(p['point'])} point; abaikan berkas *.catatan.md dan ISTILAH.md).\n"
            f"Rujukan:\n{rujukan_umum(ws, p)}")
    if (f / "MASUKAN.md").exists():
        teks += (f"- {rel_f}/MASUKAN.md — masukan pemilik proyek atas pertemuan ini. "
                 f"Kerjakan yang menyangkut berkasmu.\n")
    if peran == "SLIDE":
        teks += f"\nLuaran wajibmu: {rel_f}/SLIDE.md, mengikuti format wajib di prompt-mu.\n"
    else:
        jenis = p["jenis"]
        bahan = (p.get("bahan") or "").strip()
        teks += (f"\nJenis tugas pertemuan ini: {'+'.join(sorted(jenis))}.\n"
                 f"Luaran wajibmu di {rel_f}/: LATIHAN.md, KUNCI.md, QUIZ_AIKEN.txt"
                 + (", PRAKTIK.md" if "praktik" in jenis else "")
                 + (", folder lab/ (awal/, solusi/, README.md)" if "lab-kode" in jenis else "")
                 + (", folder bahan/ (awal/, jadi/, README.md)" if bahan else "")
                 + ".\n")
        if "lab-kode" in jenis:
            teks += (f"Solusi lab WAJIB kamu eksekusi sampai berhasil. Batas percobaan "
                     f"perbaikan: {env_int('LAB_MAX_PERCOBAAN', 3)}. Kalau tetap gagal, "
                     f"laporkan tahap ini gagal.\n")
        else:
            teks += "Jangan membuat folder lab/.\n"
        if bahan:
            teks += (f"\nBerkas kerja peserta yang diminta blueprint: {bahan}\n"
                     f"Setiap berkas yang ISINYA ditampilkan di point pertemuan ini wajib "
                     f"benar-benar ada di bahan/, dengan isi yang sama persis. Pemeriksa "
                     f"otomatis menolak paket yang menampilkan berkas tanpa menyerahkannya.\n")
            # Keadaan awal pertemuan ini = keadaan benar pertemuan sebelumnya.
            # Tanpa path konkret, peran akan mengarang ulang kerangka yang
            # berbeda dan kesinambungan antarhari putus.
            jadi_lalu = folder_pertemuan(ws, p["no"] - 1) / "bahan" / "jadi"
            if p["no"] > 1 and jadi_lalu.is_dir():
                teks += (f"bahan/awal/ pertemuan ini BERANGKAT dari "
                         f"{_rel(ws, jadi_lalu)} — salin isinya, lalu tandai bagian yang "
                         f"dikerjakan di pertemuan ini dengan TODO(peserta). Jangan "
                         f"mengarang kerangka baru.\n")
        else:
            teks += "Jangan membuat folder bahan/.\n"
    teks += ("\nKalau berkasmu sudah ada (paket dibangun ulang setelah point direvisi), "
             "sunting berkas yang ada sesuai perubahan point dan masukan — jangan tulis ulang "
             "dari nol.\n")
    return teks


def periksa_dan_catat(ws: Path) -> dict:
    cek = pemeriksa.periksa_proyek(ws)
    pemeriksa.tulis_laporan(ws, cek)
    monitor.emit("pemeriksaan", skor=cek["skor_rata"],
                 per_pertemuan={k: v["skor"] for k, v in cek["pertemuan"].items()})
    monitor.set_status(skor_pemeriksaan=cek["skor_rata"])
    return cek


def ekspor_satu(ws: Path, p: dict) -> list[str]:
    f = folder_pertemuan(ws, p["no"])
    try:
        exporter.gabung_handbook(f, f"Pertemuan {p['no']} — {p['judul']}")
        dibuat, padat = exporter.ekspor_pertemuan(
            f, docx=OPSI["ekspor_docx"], pptx=OPSI["ekspor_pptx"],
            xlsx=OPSI["ekspor_xlsx"])
        monitor.emit("export", label=f"PERTEMUAN-{p['no']:02d}",
                     berkas=[x.name for x in dibuat], padat=padat)
        return []
    except exporter.ExportError as e:
        return [f"EKSPOR-{p['no']:02d}: {e}"]


async def bangun_paket(ws: Path, p: dict):
    """Slide + Tugas dari point final -> handbook -> ekspor -> pemeriksa ->
    telaah paket -> satu revisi (design D6)."""
    no = p["no"]
    f = folder_pertemuan(ws, no)
    tanda = f / ".PAKET_OK"
    if tanda.exists():
        return
    nn = f"{no:02d}"
    print(f"\n>>> Pertemuan {no}: membangun paket dari {len(p['point'])} point.")
    tugas_paket = [(f"TUGAS-{nn}", prompt_paket(ws, p, "TUGAS"), roles.TUGAS,
                    budget("TUGAS", 4.0))]
    if OPSI["slide"]:
        tugas_paket.insert(0, (f"SLIDE-{nn}", prompt_paket(ws, p, "SLIDE"), roles.SLIDE,
                               budget("SLIDE", 3.0)))
    await _paralel_dengan_ulang(tugas_paket, ws, f, f"PAKET-GAGAL-{nn}")

    for g in ekspor_satu(ws, p):
        print(f"!! {g}")
    periksa_dan_catat(ws)

    # Telaah paket berjalan SETELAH pemeriksa, supaya Reviewer membaca
    # PEMERIKSAAN.md yang sudah mencakup paket ini.
    putaran = len(list((f / "review").glob("paket-r*.md"))) + 1
    rev = f / "review" / f"paket-r{putaran}.md"
    await _paralel_dengan_ulang([(
        f"REVIEWER-PAKET-{nn}-r{putaran}",
        (("Mode paket. Telaah konsistensi "
          + ("SLIDE.md, " if OPSI["slide"] else "")
          + "LATIHAN.md, KUNCI.md, QUIZ_AIKEN.txt")
         + (", PRAKTIK.md" if "praktik" in p["jenis"] else "")
         + (", lab/" if "lab-kode" in p["jenis"] else "")
         + f" di {_rel(ws, f)}/ terhadap point final di {_rel(ws, f)}/point/point-NN.md.\n"
         f"Baca juga docs/PEMERIKSAAN.md bagian Pertemuan {no}, docs/BLUEPRINT.md bagian "
         f"'## Pertemuan {no}' (logistik trainer), docs/KURIKULUM.md.\n"
         f"Tulis catatanmu ke {_rel(ws, rev)} dengan format wajib."),
        roles.REVIEWER, budget("PAKET_REVIEW", 2.0))], ws, f / "review", f"PAKET-GAGAL-{nn}")

    if siap_review(rev) is False:
        revisi = " ".join(butir_catatan(rev, "Revisi")).upper()
        pemilik = []
        if "SLIDE" in revisi and OPSI["slide"]:
            pemilik.append(("SLIDE", roles.SLIDE, budget("SLIDE", 3.0)))
        if any(x in revisi for x in ("LATIHAN", "KUNCI", "QUIZ", "AIKEN", "PRAKTIK",
                                     "LAB", "BAHAN", "SOAL")):
            pemilik.append(("TUGAS", roles.TUGAS, budget("TUGAS", 4.0)))
        if not pemilik:       # tidak jelas milik siapa: lebih baik keduanya membaca
            pemilik = [("TUGAS", roles.TUGAS, budget("TUGAS", 4.0))]
            if OPSI["slide"]:
                pemilik.insert(0, ("SLIDE", roles.SLIDE, budget("SLIDE", 3.0)))
        print(f">>> Telaah paket: perlu revisi — {', '.join(x[0] for x in pemilik)} memperbaiki.")
        await _paralel_dengan_ulang([
            (f"REVISI-{nama}-{nn}-r{putaran}",
             (f"Kerjakan butir di bagian 'Revisi:' pada {_rel(ws, rev)} yang menyangkut "
              f"berkasmu di {_rel(ws, f)}/. Abaikan butir untuk berkas peran lain. Sunting "
              f"berkas yang ada; point di {_rel(ws, f)}/point/ tetap sumber kebenaran — "
              f"jangan mengubah point."),
             role, biaya) for nama, role, biaya in pemilik
        ], ws, f, f"PAKET-GAGAL-{nn}")
        for g in ekspor_satu(ws, p):
            print(f"!! {g}")
        periksa_dan_catat(ws)
    tanda.write_text(datetime.now().isoformat(), encoding="utf-8")


def tulis_proses(ws: Path, p: dict) -> Path:
    """Ringkasan proses per point: putaran, status, jumlah butir revisi, skor.
    Setara 'ringkasan-proses' di alur Agent Teams pemilik proyek."""
    f = folder_pertemuan(ws, p["no"])
    baris = [f"# Proses pertemuan {p['no']} — {p['judul']}", "",
             "| Point | Judul | Status | Putaran | Butir revisi per putaran | Fakta bersih per putaran | Skor terakhir |",
             "|---|---|---|---|---|---|---|"]
    for pt in p["point"]:
        st = status_point(ws, p["no"], pt["no"])
        rw = st["riwayat"]
        baris.append(
            f"| {pt['no']} | {pt['judul'][:50]} | {st['status']} | {len(rw)} | "
            f"{' → '.join(str(x.get('revisi', '?')) for x in rw) or '-'} | "
            f"{' → '.join('ya' if x.get('fakta') else 'tidak' for x in rw) or '-'} | "
            f"{' '.join(f'{a}={b}' for a, b in (rw[-1].get('skor') or {}).items()) if rw else '-'} |")
    out = f / "PROSES.md"
    out.write_text("\n".join(baris) + "\n", encoding="utf-8")
    return out


async def gate_pertemuan(ws: Path, p: dict) -> str:
    no = p["no"]
    f = folder_pertemuan(ws, no)
    eskalasi, pertanyaan = [], []
    for pt in p["point"]:
        st = status_point(ws, no, pt["no"])
        rev = berkas_review(f, pt["no"], st["ditelaah"])
        if st["status"] == "eskalasi":
            eskalasi.append(f"- point {pt['no']} \"{pt['judul'][:50]}\": catatan terakhir "
                            f"{_rel(ws, rev)}")
        for q in butir_catatan(rev, "Perlu dicek-ditanyakan"):
            pertanyaan.append(f"- [point {pt['no']}, Reviewer] {q}")
        for q in pertanyaan_writer(berkas_catatan(f, pt["no"])):
            pertanyaan.append(f"- [point {pt['no']}, Writer] {q}")
    paket = sorted((f / "review").glob("paket-r*.md"))
    for q in (butir_catatan(paket[-1], "Perlu dicek-ditanyakan") if paket else []):
        pertanyaan.append(f"- [paket, Reviewer] {q}")
    berkas_tanya = f / "PERTANYAAN.md"
    berkas_tanya.write_text(f"# Pertanyaan pertemuan {no}\n\n"
                            + ("\n".join(pertanyaan) if pertanyaan else "Tidak ada.") + "\n",
                            encoding="utf-8")
    proses = tulis_proses(ws, p)

    cek = (pemeriksa.baca_hasil(ws) or {}).get("pertemuan", {}).get(str(no), {})
    gagal_cek = [x for x in cek.get("hasil", []) if x["status"] == pemeriksa.GAGAL]
    status_paket = ("Siap" if paket and siap_review(paket[-1]) else
                    "Perlu revisi (sudah diperbaiki satu kali)" if paket else "?")
    biaya = sum(v for kk, v in (monitor._status.get("cost") or {}).items()
                if kk != "total" and f"-{no:02d}" in kk)
    tanya = (
        f"PERTEMUAN {no} — {p['judul']} selesai: {len(p['point'])} point, paket di "
        f"{_rel(ws, f)}/\n"
        f"Skor pemeriksaan otomatis: {cek.get('skor', '?')}% (docs/PEMERIKSAAN.md)"
        + ("\n" + "\n".join(f"  ✗ {x['nama']}: {x['bukti'][:120]}" for x in gagal_cek) if gagal_cek else "")
        + f"\nTelaah paket: {status_paket}\n"
        + ("\nPoint yang DIESKALASI (belum siap setelah batas putaran):\n" + "\n".join(eskalasi) + "\n"
           if eskalasi else "")
        + (f"\nPertanyaan terkumpul ({len(pertanyaan)}), lengkap di {_rel(ws, berkas_tanya)}:\n"
           + "\n".join(pertanyaan[:10]) + ("\n..." if len(pertanyaan) > 10 else "") + "\n"
           if pertanyaan else "")
        + f"\nRingkasan proses per point: {_rel(ws, proses)}\n"
        f"Biaya pertemuan ini: ${biaya:.2f} · kumulatif proyek: ${biaya_total():.2f}\n\n"
        "'y' = setuju, lanjut ke pertemuan berikutnya; teks = masukan/jawaban pertanyaan "
        "(point yang terkena direvisi, paket dibangun ulang); 'q' = berhenti.")
    return await gate(tanya, label=f"PERTEMUAN-{no}",
                      files=[x for x in (f / "HANDBOOK.docx", f / "HANDBOOK.md",
                                        f / "SLIDE.pptx", berkas_tanya) if x.exists()][:3])


async def revisi_masukan(ws: Path, p: dict, ans: str):
    """Masukan teks di gate pertemuan: Writer merevisi point yang terkena, point
    itu ditelaah ulang, lalu paket dibangun ulang."""
    no = p["no"]
    f = folder_pertemuan(ws, no)
    masukan = f / "MASUKAN.md"
    lama = masukan.read_text(encoding="utf-8") if masukan.exists() else f"# Masukan pertemuan {no}\n"
    masukan.write_text(lama + f"\n## Masukan {datetime.now():%d %b %H:%M}\n{ans}\n", encoding="utf-8")

    sebelum = {pt["no"]: berkas_point(f, pt["no"]).stat().st_mtime
               for pt in p["point"] if berkas_point(f, pt["no"]).exists()}
    ke = len(re.findall(r"^## Masukan", masukan.read_text(encoding="utf-8"), re.M))
    await run_stage_retry(
        f"WRITER-{no:02d}-MASUKAN-{ke}",
        (f"Pemilik proyek memberi masukan atas pertemuan {no} di {_rel(ws, masukan)} (bagian "
         f"terakhir). Masukan itu bisa berupa koreksi atau jawaban atas pertanyaan di "
         f"{_rel(ws, f / 'PERTANYAAN.md')}.\n"
         f"Tentukan point mana di {_rel(ws, f / 'point')}/ yang terkena, lalu sunting HANYA "
         f"point itu dengan Edit. Jangan menyentuh point yang tidak terkena. Kalau masukan "
         f"hanya menyangkut slide atau tugas, jangan mengubah point apa pun.\n\n"
         f"Rujukan:\n{rujukan_umum(ws, p)}\nSebut di laporan akhir point mana yang kamu ubah."),
        roles.WRITER, ws, budget("POINT_WRITER", 4.0), wilayah=f / "point")

    berubah = [pt for pt in p["point"] if berkas_point(f, pt["no"]).exists()
               and berkas_point(f, pt["no"]).stat().st_mtime != sebelum.get(pt["no"])]
    print(f">>> Point yang direvisi: {', '.join(str(pt['no']) for pt in berubah) or 'tidak ada'}.")
    for pt in berubah:
        # Writer sudah menulis revisinya; siklus baru dimulai dari telaah.
        mulai_siklus_baru(ws, no, pt["no"], None, sudah_ditulis=True)
        await produksi_point(ws, p, pt)
    (f / ".PAKET_OK").unlink(missing_ok=True)


async def produksi_pertemuan(ws: Path, p: dict, pilot: bool):
    f = folder_pertemuan(ws, p["no"])
    if (f / ".GATE_OK").exists():
        return
    f.mkdir(parents=True, exist_ok=True)
    monitor.set_status(pertemuan=p["no"], pertemuan_judul=p["judul"][:80])
    print(f"\n{'=' * 70}\n>>> PERTEMUAN {p['no']} — {p['judul']}: {len(p['point'])} point, "
          f"tugas {'+'.join(sorted(p['jenis']))}\n{'=' * 70}")
    for pt in p["point"]:
        await produksi_point(ws, p, pt)
        if pilot and pt["no"] == 1:
            await gate_pilot(ws, p, pt)
        await cek_plafon_proyek()

    while True:
        await bangun_paket(ws, p)
        ans = await gate_pertemuan(ws, p)
        if ans.lower() == "y":
            (f / ".GATE_OK").write_text(datetime.now().isoformat(), encoding="utf-8")
            return
        await revisi_masukan(ws, p, ans)
        await cek_plafon_proyek()


async def tambah_slide(ws: Path, nomor: int | None):
    """Buat SLIDE.md menyusul untuk pertemuan yang paketnya sudah jadi.

    Dipakai kalau proyek dibuat dengan opsi slide dimatikan, lalu pemiliknya
    berubah pikiran. Point tidak disentuh: slide memang dibangun dari point
    final, jadi menambahkannya belakangan tidak mengubah isi materi.
    """
    global OPSI
    OPSI = {**opsi_mod.baca(ws), "slide": True}
    semua = daftar_pertemuan(ws)
    target = [p for p in semua if nomor is None or p["no"] == nomor]
    if not target:
        print(f"!! Pertemuan {nomor} tidak ada di blueprint.")
        raise SystemExit(1)

    dikerjakan = []
    for p in target:
        f = folder_pertemuan(ws, p["no"])
        if not list((f / "point").glob("point-[0-9][0-9].md")):
            print(f">>> Pertemuan {p['no']} belum punya point — dilewati.")
            continue
        if (f / "SLIDE.md").exists():
            print(f">>> Pertemuan {p['no']} sudah punya SLIDE.md — dilewati.")
            continue
        nn = f"{p['no']:02d}"
        print(f"\n>>> Membuat slide susulan untuk pertemuan {p['no']}.")
        await _paralel_dengan_ulang(
            [(f"SLIDE-{nn}", prompt_paket(ws, p, "SLIDE"), roles.SLIDE, budget("SLIDE", 3.0))],
            ws, f, f"SLIDE-GAGAL-{nn}")
        for g in ekspor_satu(ws, p):
            print(f"!! {g}")
        dikerjakan.append(p["no"])
        await cek_plafon_proyek()

    if dikerjakan:
        # Opsi proyek diperbarui supaya produksi berikutnya ikut membuat slide.
        opsi_mod.tulis(ws, {**opsi_mod.baca(ws), "slide": True})
        cek = periksa_dan_catat(ws)
        print(f"\n>>> Slide dibuat untuk pertemuan: "
              f"{', '.join(map(str, dikerjakan))}. Skor pemeriksaan {cek['skor_rata']}%.")
    else:
        print(">>> Tidak ada pertemuan yang perlu dibuatkan slide.")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def tulis_state(ws: Path, tahap: str):
    (ws / "docs" / "STATE.txt").write_text(tahap, encoding="utf-8")


def baca_state(ws: Path) -> str | None:
    p = ws / "docs" / "STATE.txt"
    if not p.exists():
        return None
    s = p.read_text(encoding="utf-8").strip()
    # Tahap alur lama (sebelum produksi per point) dipetakan ke produksi.
    return "produksi" if s in ("pilot", "telaah") else s


async def pipeline(ws: Path, project: str, teks_silabus: str, mulai: str, pilot_no: int | None):
    global SESSIONS, OPSI
    docs = ws / "docs"
    SESSIONS = Sessions(docs)
    OPSI = opsi_mod.baca(ws)
    print(f"Opsi proyek : {opsi_mod.ringkas(OPSI)}")
    idx = TAHAP.index(mulai)

    # --- Tahap 1: Kurikulum -> gate --------------------------------------
    if idx <= TAHAP.index("kurikulum"):
        tulis_state(ws, "kurikulum")
        fb = docs / "KURIKULUM_FEEDBACK.md"
        prompt = (
            "Baca sumber/silabus.txt"
            + (" dan docs/KLIEN.md" if (docs / "KLIEN.md").exists() else "")
            + ", lalu tulis docs/KURIKULUM.md dan docs/GLOSARIUM.md sesuai peranmu.\n"
            + (f"\nAda masukan manusia atas versimu sebelumnya di "
               f"{fb.name} — baca dan kerjakan.\n" if fb.exists() else "")
        )
        # Teks silabus yang benar-benar dibaca peran ditampilkan di gate ini.
        # Ini yang membuat ekstraksi PDF/DOCX yang berantakan tertangkap sebelum
        # biaya produksi keluar. Ditampilkan UTUH: kerusakan ekstraksi justru
        # paling sering muncul di tabel dan bagian bawah dokumen, jadi memotong
        # di baris ke-25 membuang tepat bagian yang perlu diperiksa.
        cuplikan = ("Teks silabus yang dibaca peran (dari sumber/silabus.txt):\n"
                    "-----\n" + teks_silabus.strip() + "\n-----")
        # Berkas sumbernya ikut dilampirkan: teks persis yang dibaca peran, tanpa
        # lewat escape HTML, dan bisa digulir tanpa membanjiri chat. Yang
        # dilampirkan adalah silabus.txt hasil ekstraksi — BUKAN berkas asli
        # .pdf/.docx di sebelahnya, karena justru hasil ekstraksinya yang perlu
        # diperiksa benar atau tidak.
        sumber = ws / "sumber" / "silabus.txt"
        await doc_with_gate("KURIKULUM", "KURIKULUM", prompt, roles.KURIKULUM, ws,
                            budget("KURIKULUM", 2.0),
                            lampiran=([sumber] if sumber.exists() else [])
                                     + [docs / "GLOSARIUM.md"],
                            tambahan_gate=cuplikan)
        await cek_plafon_proyek()

    # --- Tahap 2: Blueprint -> gate --------------------------------------
    if idx <= TAHAP.index("blueprint"):
        tulis_state(ws, "blueprint")
        fb = docs / "BLUEPRINT_FEEDBACK.md"
        prompt = (
            "Baca docs/KURIKULUM.md, docs/GLOSARIUM.md, dan sumber/silabus.txt"
            + (", dan docs/KLIEN.md" if (docs / "KLIEN.md").exists() else "")
            + ", lalu tulis docs/BLUEPRINT.md sesuai peranmu. Salin point dari silabus "
              "apa adanya ke bagian '### Point' tiap pertemuan.\n"
            + (f"\nAda masukan manusia atas versimu sebelumnya di "
               f"{fb.name} — baca dan kerjakan.\n" if fb.exists() else "")
        )
        await doc_with_gate("BLUEPRINT", "BLUEPRINT", prompt, roles.BLUEPRINT, ws,
                            budget("BLUEPRINT", 3.0), ringkas_fn=lambda: ringkas_blueprint(ws),
                            telaah_fn=lambda: telaah_blueprint(ws))
        await cek_plafon_proyek()

    pertemuan = daftar_pertemuan(ws)
    kosong = [p["no"] for p in pertemuan if not p["point"]]
    if not pertemuan or kosong:
        print("!! " + ("Tidak ada '## Pertemuan <n>' di docs/BLUEPRINT.md." if not pertemuan else
                       f"Pertemuan {', '.join(map(str, kosong))} tidak punya '### Point' yang "
                       f"terbaca.")
              + " Perbaiki blueprint lalu jalankan ulang dengan --resume blueprint.")
        raise SystemExit(1)
    jml_point = sum(len(p["point"]) for p in pertemuan)
    print(f"\n>>> {len(pertemuan)} pertemuan, {jml_point} point di blueprint.")
    monitor.set_status(pertemuan_total=len(pertemuan), point_total=jml_point)

    pilot = next((p for p in pertemuan if p["no"] == pilot_no), None) if pilot_no else pertemuan[0]
    if pilot_no and not pilot:
        print(f"!! Pertemuan {pilot_no} tidak ada di blueprint. "
              f"Memakai pertemuan {pertemuan[0]['no']} sebagai pilot.")
        pilot = pertemuan[0]

    # --- Tahap 3: Produksi per pertemuan, per point ----------------------
    # Pilot dikerjakan lebih dulu walau nomornya bukan yang pertama: gate
    # gaya harus lewat sebelum point lain ditulis.
    if idx <= TAHAP.index("produksi"):
        tulis_state(ws, "produksi")
        urutan = [pilot] + [p for p in pertemuan if p["no"] != pilot["no"]]
        for p in urutan:
            await produksi_pertemuan(ws, p, pilot=p["no"] == pilot["no"])
            monitor.set_status(pertemuan_selesai=sum(
                1 for x in pertemuan if (folder_pertemuan(ws, x["no"]) / ".GATE_OK").exists()))

    # --- Tahap 4: Akhir — Editor menyeragamkan istilah -------------------
    tulis_state(ws, "akhir")
    print("\n>>> Tahap akhir: Editor menggabungkan glosarium dan menyeragamkan istilah.")
    try:
        await run_stage_retry("EDITOR", (
            "Gabungkan semua berkas ISTILAH.md di bawah materi/ ke docs/GLOSARIUM.md, "
            "seragamkan istilah di berkas sumber (point/point-*.md, SLIDE.md, LATIHAN.md, "
            "KUNCI.md, PRAKTIK.md), lalu tulis docs/TELAAH_BAHASA.md sesuai peranmu. "
            "Jangan menyunting HANDBOOK.md — ia dibentuk ulang otomatis dari point."
        ), roles.EDITOR, ws, budget("EDITOR", 4.0))
    except StageFailed as e:
        print(f"!! EDITOR gagal: {e} — materi tetap dipakai tanpa penyeragaman.")

    # Editor menyunting point, jadi handbook dan biner dibentuk ulang.
    for p in pertemuan:
        for g in ekspor_satu(ws, p):
            print(f"!! {g}")
    cek = periksa_dan_catat(ws)

    # --- Ringkasan akhir ---------------------------------------------------
    tulis_state(ws, "selesai")
    semua = status_semua(ws)
    siap = sum(1 for v in semua.values() if v.get("status") == "siap")
    eskal = [k for k, v in semua.items() if v.get("status") == "eskalasi"]
    skor = [v["riwayat"][-1]["skor"] for v in semua.values()
            if v.get("riwayat") and v["riwayat"][-1].get("skor")]
    rata = {d: round(sum(s.get(d, 0) for s in skor) / len(skor), 2)
            for d in ("akurasi", "capaian", "keterbacaan", "koherensi")} if skor else {}
    belum = [p["no"] for p in pertemuan if not (folder_pertemuan(ws, p["no"]) / ".GATE_OK").exists()]
    ringkas = [
        "",
        "=" * 70,
        f"SELESAI — proyek '{project}'",
        f"Pertemuan             : {len(pertemuan)} (belum disetujui: {', '.join(map(str, belum)) or '-'})",
        f"Point                 : {jml_point} (siap {siap}, eskalasi {len(eskal)}"
        + (f": {', '.join(eskal)}" if eskal else "") + ")",
        f"Skor pemeriksaan      : {cek['skor_rata']}%",
        f"Skor Reviewer rata-rata: {rata or '-'}",
        f"Biaya total           : ${biaya_total():.2f}",
        f"Materi                : {(ws / 'materi')}",
        "=" * 70,
    ]
    print("\n".join(ringkas))
    monitor.tg_send(monitor.form(f"🎉 Selesai — {project}", [
        ("Pertemuan", f"{len(pertemuan)}" + (f" (belum disetujui: {', '.join(map(str, belum))})"
                                             if belum else "")),
        ("Point", f"{jml_point} · siap {siap}" + (f" · eskalasi {len(eskal)}" if eskal else "")),
        ("Skor pemeriksaan", f"{cek['skor_rata']}%"),
        ("Skor Reviewer", " ".join(f"{a}={b}" for a, b in rata.items()) if rata else None),
        ("Biaya", f"${biaya_total():.2f}"),
    ], f"Materi ada di {(ws / 'materi')}"), html=True)
    monitor.emit("info", msg="pipeline selesai", biaya=biaya_total(), point=jml_point,
                 siap=siap, eskalasi=eskal, skor_reviewer=rata)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Produksi materi ajar dari silabus.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("silabus", nargs="?",
                    help="path berkas silabus (.md/.txt/.docx/.pdf) atau teks silabus langsung")
    ap.add_argument("--project", help="nama proyek di workspace/ (bawaan: dari judul silabus)")
    ap.add_argument("--resume", choices=TAHAP,
                    help="mulai dari tahap tertentu, memakai dokumen yang sudah ada")
    ap.add_argument("--pilot", type=int,
                    help="nomor pertemuan yang point pertamanya dijadikan pilot "
                         "(bawaan: pertemuan pertama)")
    ap.add_argument("--klien", help="berkas .md konteks klien (industri, audiens, tool, "
                                    "aturan gaya khusus); disalin ke docs/KLIEN.md")
    ap.add_argument("--slide", metavar="N|semua",
                    help="buat SLIDE.md menyusul untuk pertemuan N (atau 'semua'), "
                         "lalu berhenti — untuk proyek yang dibuat tanpa slide")
    a = ap.parse_args()

    if not a.silabus and not a.project:
        ap.error("beri path/teks silabus, atau --project untuk melanjutkan proyek yang ada.")

    # Silabus: dari argumen, atau dari jejak sumber proyek yang dilanjutkan.
    if a.silabus:
        try:
            teks, asli = silabus_mod.baca(a.silabus)
        except silabus_mod.SilabusError as e:
            print(f"Silabus tidak bisa dipakai: {e}")
            sys.exit(2)
    else:
        simpan = WS / a.project / "sumber" / "silabus.txt"
        if not simpan.exists():
            print(f"Proyek '{a.project}' tidak punya {simpan}. "
                  f"Jalankan sekali dengan path silabus.")
            sys.exit(2)
        teks, asli = simpan.read_text(encoding="utf-8"), None

    global CLI_PATH
    CLI_PATH = cari_cli()

    ws, project = silabus_mod.siapkan(teks, asli, a.project)
    monitor.init(ws / "docs", project)
    # Sisa gate dan jawaban dari proses sebelumnya yang mati tidak boleh
    # terbawa ke jalannya pipeline yang baru.
    monitor.set_status(gate=None)
    monitor.buang_jawaban_tertinggal()
    if a.klien:
        sumber_klien = Path(a.klien)
        if not sumber_klien.is_file():
            print(f"Berkas konteks klien tidak ada: {sumber_klien}")
            sys.exit(2)
        shutil.copyfile(sumber_klien, ws / "docs" / "KLIEN.md")

    mulai = a.resume or baca_state(ws) or "kurikulum"
    if mulai == "selesai":
        mulai = "akhir"        # proyek selesai yang dijalankan lagi = ulang tahap akhir
    if mulai not in TAHAP:
        mulai = "kurikulum"

    ok, pesan = lock_acquire(project, f"slide:{a.slide}" if a.slide else
                             (f"resume:{mulai}" if a.resume else "jalan"))
    if not ok:
        print(pesan)
        sys.exit(1)

    print("=" * 70)
    print(f"AI ACADEMY — proyek '{project}'")
    print(f"Ruang kerja : {ws}")
    print(f"Silabus     : {asli.name if asli else 'teks langsung'} "
          f"({len(teks.splitlines())} baris)")
    print(f"Autentikasi : {auth_mode()}")
    print(f"Claude CLI  : {CLI_PATH or '(pencarian bawaan SDK)'}")
    print(f"Mulai dari  : {'slide susulan ' + str(a.slide) if a.slide else mulai}")
    print(f"Pilot       : point 1 {'pertemuan ' + str(a.pilot) if a.pilot else 'pertemuan pertama'}")
    print(f"Klien       : {'docs/KLIEN.md' if (ws / 'docs' / 'KLIEN.md').exists() else '-'}")
    print(f"Point       : {opsi_mod.baca(ws)['point_halaman']} halaman, "
          f"maks. {opsi_mod.baca(ws)['point_maks_putaran']} putaran")
    print("=" * 70)
    monitor.tg_send(monitor.form("🎓 AI Academy mulai", [
        ("Proyek", project),
        ("Mulai dari", "slide susulan " + str(a.slide) if a.slide else mulai),
        ("Silabus", asli.name if asli else "teks langsung"),
        ("Akun", akun_claude() or auth_mode()),
    ]), html=True)

    try:
        if a.slide:
            nomor = None if str(a.slide).lower() in ("semua", "all") else int(a.slide)
            asyncio.run(tambah_slide(ws, nomor))
        else:
            asyncio.run(pipeline(ws, project, teks, mulai, a.pilot))
    except KeyboardInterrupt:
        print("\nDihentikan dari keyboard. Dokumen yang sudah ada tetap tersimpan.")
        monitor.emit("info", msg="dihentikan dari keyboard")
    except StageFailed as e:
        print(f"\nBerhenti: {e}\nLanjutkan nanti dengan: "
              f"python academy.py --project {project} --resume {baca_state(ws) or 'kurikulum'}")
        monitor.emit("error", error=str(e))
        sys.exit(1)
    finally:
        lock_release(project)
        monitor.set_status(gate=None, current=None)


if __name__ == "__main__":
    main()
