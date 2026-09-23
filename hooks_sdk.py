"""Hook Agent SDK yang menegakkan aturan saat itu juga, bukan di telaah akhir.

Aturan yang hanya ditulis di prompt ("jangan tulis di luar folder pertemuanmu",
"jangan buat .docx", "maksimal 6 butir per slide") baru ketahuan dilanggar
setelah seluruh pertemuan jadi — tempat termahal untuk memperbaikinya. Hook di
sini memeriksanya di setiap pemanggilan tool:

- PreToolUse  Write/Edit : tolak penulisan di luar wilayah peran dan penulisan
                           berkas biner, dengan alasan yang bisa ditindaklanjuti.
- PreToolUse  Bash       : tolak perintah terlarang (juga dicegah oleh
                           disallowed_tools; di sini supaya penolakannya TERCATAT).
- PostToolUse Write/Edit : begitu SLIDE.md ditulis, periksa kepadatannya dan
                           kembalikan pelanggarannya ke peran Slide.

Ini hook Python milik SDK, bukan `.claude/settings.json`: pipeline memanggil SDK
dengan setting_sources=[], jadi hook dari berkas setelan tidak pernah dimuat.
"""
import fnmatch
from pathlib import Path

import exporter
import monitor
import roles

TOOL_TULIS = "Write|Edit|MultiEdit|NotebookEdit"
BINER = {".docx", ".pptx", ".xlsx", ".pdf"}

# "Bash(rm -rf *)" -> "rm -rf *"
POLA_TERLARANG = [p[5:-1] for p in roles.DENY_BASH if p.startswith("Bash(") and p.endswith(")")]


def _tolak(label: str, tool: str, sasaran: str, alasan: str) -> dict:
    monitor.emit("tool_denied", label=label, tool=tool, target=sasaran[:200], alasan=alasan)
    print(f"  [{label}] DITOLAK {tool} {sasaran[:80]} — {alasan[:100]}")
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": alasan,
    }}


def _path_sasaran(tool_input: dict, ws: Path) -> Path | None:
    mentah = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not mentah:
        return None
    p = Path(mentah)
    if not p.is_absolute():
        p = ws / p
    try:
        return p.resolve()
    except OSError:
        return p


def _di_dalam(p: Path, dasar: Path) -> bool:
    dasar = dasar.resolve()
    return p == dasar or dasar in p.parents


def buat_hooks(label: str, ws: Path, wilayah: Path | None) -> dict:
    """Hook untuk satu tahap.

    `wilayah` adalah folder tempat peran ini boleh menulis. None berarti seluruh
    ruang kerja proyek (tetap tidak boleh keluar dari proyek).
    """
    ws = ws.resolve()
    batas = (wilayah or ws).resolve()
    rel_batas = batas.relative_to(ws).as_posix() if batas != ws else "ruang kerja proyek"

    async def jaga_tulis(inp, tool_use_id, context):
        tool = inp.get("tool_name", "")
        p = _path_sasaran(inp.get("tool_input") or {}, ws)
        if p is None:
            return {}
        sasaran = p.as_posix()

        if p.suffix.lower() in BINER:
            return _tolak(label, tool, sasaran,
                          f"Jangan menulis berkas {p.suffix} langsung. Tulis sumber Markdown "
                          f"saja; exporter.py menghasilkan berkas biner darinya.")
        if not _di_dalam(p, ws):
            return _tolak(label, tool, sasaran,
                          "Berkas ini di luar ruang kerja proyek. Semua pekerjaanmu harus "
                          f"berada di dalam {ws.as_posix()}.")
        if not _di_dalam(p, batas):
            if p.name == "GLOSARIUM.md":
                alasan = ("Jangan menulis docs/GLOSARIUM.md — beberapa pertemuan diproduksi "
                          "bersamaan dan akan saling menimpa. Tulis istilah barumu ke "
                          f"{rel_batas}/ISTILAH.md; Editor yang menggabungkannya.")
            else:
                alasan = (f"Peran ini hanya boleh menulis di {rel_batas}/. "
                          f"Berkas {p.relative_to(ws).as_posix()} milik peran lain.")
            return _tolak(label, tool, sasaran, alasan)
        return {}

    async def jaga_bash(inp, tool_use_id, context):
        cmd = ((inp.get("tool_input") or {}).get("command") or "").strip()
        for pola in POLA_TERLARANG:
            if fnmatch.fnmatch(cmd, pola):
                return _tolak(label, "Bash", cmd,
                              f"Perintah ini terlarang untuk semua peran (pola '{pola}').")
        return {}

    async def periksa_slide(inp, tool_use_id, context):
        p = _path_sasaran(inp.get("tool_input") or {}, ws)
        if p is None or p.name != "SLIDE.md" or not p.exists():
            return {}
        try:
            _, slides = exporter.parse_slides(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not slides:
            pesan = ("SLIDE.md tidak memuat satu slide pun. Setiap slide harus diawali "
                     "baris '## <judul slide>'. Perbaiki sebelum selesai.")
        else:
            temuan = exporter.periksa_kepadatan(slides, p)
            if not temuan:
                return {}
            pesan = ("SLIDE.md melanggar batas kepadatan. Perbaiki SEKARANG sebelum "
                     "selesai — pecah slide yang terlalu padat, jangan hapus isinya:\n"
                     + "\n".join(f"- {t}" for t in temuan[:15]))
        monitor.emit("info", label=label, msg="umpan balik kepadatan slide",
                     detail=pesan[:300])
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                       "additionalContext": pesan}}

    from claude_agent_sdk import HookMatcher

    return {
        "PreToolUse": [HookMatcher(matcher=TOOL_TULIS, hooks=[jaga_tulis]),
                       HookMatcher(matcher="Bash", hooks=[jaga_bash])],
        "PostToolUse": [HookMatcher(matcher=TOOL_TULIS, hooks=[periksa_slide])],
    }
