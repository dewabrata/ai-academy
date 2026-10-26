"""Batas kuota dari SDK membuat pipeline MENUNGGU, bukan mati.

Dijalankan dari akar repo:  ./.venv/Scripts/python.exe uji/uji_kuota_sdk.py

Kejadian 26 Okt 2026: pipeline mati di tahap blueprint dengan
    claude_agent_sdk._errors.ResultError:
    Claude Code returned an error result: You've hit your session limit
padahal QUOTA_WAIT=auto. Sebabnya galat itu DILEMPAR oleh iterator SDK, bukan
datang sebagai pesan, sehingga tidak pernah menjadi StageFailed - satu-satunya
jenis yang ditangkap run_stage_retry. POLA_KUOTA tidak pernah sempat membacanya.
"""
import asyncio
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from claude_agent_sdk import ClaudeSDKError, ResultError  # noqa: E402

import academy  # noqa: E402

gagal = 0


def cek(nama, kondisi, info=""):
    global gagal
    print(("  ok   " if kondisi else "  GAGAL") + f" {nama}"
          + (f" - {info}" if info and not kondisi else ""))
    gagal += not kondisi


PESAN = ("Claude Code returned an error result: "
         "You've hit your session limit · resets 5:20am (Asia/Jakarta)")

print("Pengenalan teks batas kuota")
for teks, harap in [
    (PESAN, True),
    ("Claude Code returned an error result: You've hit your usage limit", True),
    ("rate limit exceeded", True),
    ("HTTP 429 Too Many Requests", True),
    ("quota exhausted", True),
    ("TypeError: unsupported operand", False),
    ("ENOTFOUND api.anthropic.com", False),
]:
    cek(f"{'kuota' if harap else 'bukan kuota'}: {teks[:46]}",
        academy.kena_kuota(Exception(teks)) is harap)

print("\nGalat jaringan tetap dibedakan dari kuota")
for teks in ("ENOTFOUND api.anthropic.com", "socket hang up", "ECONNRESET"):
    cek(f"jaringan: {teks}", academy.kena_jaringan(Exception(teks)))

print("\nGalat yang DILEMPAR SDK menjadi StageFailed")
cek("ResultError turunan ClaudeSDKError", issubclass(ResultError, ClaudeSDKError))

sumber = (AKAR / "academy.py").read_text(encoding="utf-8")
cek("run_stage menangkap ClaudeSDKError", "except ClaudeSDKError as e:" in sumber)
cek("diubah jadi StageFailed", "raise StageFailed(f\"{label}: {e}\") from e" in sumber)
cek("query() berada di dalam try",
    sumber.index("    try:\n        async for msg in query(")
    < sumber.index("except ClaudeSDKError"))


class _Palsu:
    """Meniru iterator SDK yang melempar di tengah jalan."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise ResultError(PESAN, exit_code=1)


async def _coba():
    """Jalur yang sama seperti run_stage: iterasi lalu galat dilempar."""
    try:
        async for _ in _Palsu():
            pass
    except ClaudeSDKError as e:
        raise academy.StageFailed(f"BLUEPRINT: {e}") from e


try:
    asyncio.run(_coba())
    cek("ResultError tertangkap sebagai StageFailed", False, "tidak melempar")
except academy.StageFailed as e:
    cek("ResultError tertangkap sebagai StageFailed", True)
    cek("pesannya masih memuat sebab aslinya", "session limit" in str(e), str(e)[:70])
    # Inilah yang sebelumnya tidak pernah terjadi: run_stage_retry hanya
    # menangkap StageFailed, jadi kena_kuota() tidak pernah dipanggil.
    cek("dikenali sebagai kuota -> pipeline akan menunggu", academy.kena_kuota(e))
    cek("tidak disangka galat jaringan", not academy.kena_jaringan(e))
except Exception as e:
    cek("ResultError tertangkap sebagai StageFailed", False, f"{type(e).__name__}: {e}")

print("")
print("SEMUA LULUS" if not gagal else f"{gagal} GAGAL")
sys.exit(1 if gagal else 0)
