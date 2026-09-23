"""Membaca dan menulis setelan `.env` untuk dashboard.

Tiga aturan yang menjaga supaya menyunting setelan dari browser tidak berbahaya:

1. **Daftar putih.** Hanya kunci di `KUNCI` yang boleh ditulis. Permintaan yang
   menyebut kunci lain diabaikan, bukan ditulis diam-diam.
2. **Rahasia tidak pernah keluar.** Token dan kata sandi dikirim ke browser
   hanya sebagai status `terisi`/`kosong`. Kolom kosong berarti "biarkan nilai
   lama", bukan "kosongkan".
3. **Berkas dipertahankan.** Komentar dan urutan baris `.env` tidak diubah;
   kunci yang belum ada ditambahkan di akhir.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ENV = Path(__file__).parent / ".env"

# grup, label, tipe (teks|angka|sandi|pilihan), pilihan
KUNCI: dict[str, dict] = {
    "TELEGRAM_BOT_TOKEN": dict(grup="Telegram", label="Bot token", tipe="sandi"),
    "TELEGRAM_CHAT_ID": dict(grup="Telegram", label="Chat ID", tipe="teks"),

    "MODEL_KURIKULUM": dict(grup="Model", label="Kurikulum", tipe="teks"),
    "MODEL_BLUEPRINT": dict(grup="Model", label="Blueprint", tipe="teks"),
    "MODEL_WRITER": dict(grup="Model", label="Writer", tipe="teks"),
    "MODEL_REVIEWER": dict(grup="Model", label="Reviewer", tipe="teks"),
    "MODEL_FAKTA": dict(grup="Model", label="Fact-Checker", tipe="teks"),
    "MODEL_SLIDE": dict(grup="Model", label="Slide", tipe="teks"),
    "MODEL_TUGAS": dict(grup="Model", label="Tugas", tipe="teks"),
    "MODEL_EDITOR": dict(grup="Model", label="Editor", tipe="teks"),

    "BUDGET_KURIKULUM": dict(grup="Biaya", label="Kurikulum", tipe="angka"),
    "BUDGET_BLUEPRINT": dict(grup="Biaya", label="Blueprint", tipe="angka"),
    "BUDGET_POINT_WRITER": dict(grup="Biaya", label="Writer / point", tipe="angka"),
    "BUDGET_POINT_REVIEW": dict(grup="Biaya", label="Reviewer / point", tipe="angka"),
    "BUDGET_POINT_FAKTA": dict(grup="Biaya", label="Fact-Checker / point", tipe="angka"),
    "BUDGET_SLIDE": dict(grup="Biaya", label="Slide / pertemuan", tipe="angka"),
    "BUDGET_TUGAS": dict(grup="Biaya", label="Tugas / pertemuan", tipe="angka"),
    "BUDGET_PAKET_REVIEW": dict(grup="Biaya", label="Telaah paket", tipe="angka"),
    "BUDGET_EDITOR": dict(grup="Biaya", label="Editor", tipe="angka"),
    "BUDGET_PROYEK": dict(grup="Biaya", label="Plafon total proyek", tipe="angka"),

    "POINT_HALAMAN": dict(grup="Produksi", label="Panjang point (halaman)", tipe="teks"),
    "POINT_MAKS_PUTARAN": dict(grup="Produksi", label="Maks. putaran telaah", tipe="angka"),
    "LAB_MAX_PERCOBAAN": dict(grup="Produksi", label="Percobaan lab", tipe="angka"),
    "OPSI_SLIDE": dict(grup="Produksi", label="Buat slide (bawaan)", tipe="pilihan",
                       pilihan=["1", "0"]),
    "OPSI_EKSPOR_DOCX": dict(grup="Produksi", label="Ekspor DOCX (bawaan)", tipe="pilihan",
                             pilihan=["1", "0"]),
    "OPSI_EKSPOR_PPTX": dict(grup="Produksi", label="Ekspor PPTX (bawaan)", tipe="pilihan",
                             pilihan=["1", "0"]),

    "QUOTA_WAIT": dict(grup="Kuota", label="Saat kuota habis", tipe="pilihan",
                       pilihan=["auto", "ask"]),
    "QUOTA_WAIT_MAX_HOURS": dict(grup="Kuota", label="Batas menunggu (jam)", tipe="angka"),

    "DASHBOARD_USER": dict(grup="Dashboard", label="Nama pengguna", tipe="teks"),
    "DASHBOARD_PASS": dict(grup="Dashboard", label="Kata sandi", tipe="sandi"),
    "DASHBOARD_PORT": dict(grup="Dashboard", label="Port", tipe="angka"),
    "DASHBOARD_SESI_JAM": dict(grup="Dashboard", label="Umur sesi (jam)", tipe="angka"),

    "ANTHROPIC_API_KEY": dict(grup="Autentikasi", label="API key (kosong = langganan)",
                              tipe="sandi"),
    "CLAUDE_CLI_PATH": dict(grup="Autentikasi", label="Path claude.exe", tipe="teks"),
}

RAHASIA = {k for k, v in KUNCI.items() if v["tipe"] == "sandi"}


def baca() -> list[dict]:
    """Setelan untuk ditampilkan. Nilai rahasia TIDAK ikut."""
    out = []
    for kunci, meta in KUNCI.items():
        nilai = (os.getenv(kunci) or "").strip()
        out.append({"kunci": kunci, **meta,
                    "nilai": "" if kunci in RAHASIA else nilai,
                    "terisi": bool(nilai)})
    return out


def tulis(perubahan: dict) -> tuple[bool, str]:
    """Tulis nilai baru ke `.env`. Kunci rahasia dengan nilai kosong dilewati."""
    bersih = {}
    for kunci, nilai in (perubahan or {}).items():
        if kunci not in KUNCI:
            continue                     # daftar putih
        nilai = str(nilai if nilai is not None else "").strip()
        if kunci in RAHASIA and not nilai:
            continue                     # kosong = biarkan nilai lama
        if "\n" in nilai or "\r" in nilai:
            return False, f"Nilai {kunci} tidak boleh memuat baris baru."
        bersih[kunci] = nilai
    if not bersih:
        return False, "Tidak ada setelan yang berubah."

    baris = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    sisa = dict(bersih)
    for i, b in enumerate(baris):
        kunci = b.split("=", 1)[0].strip()
        if kunci in sisa:
            baris[i] = f"{kunci}={sisa.pop(kunci)}"
    if sisa:
        baris += ["", "# Ditambahkan dari dashboard"]
        baris += [f"{k}={v}" for k, v in sisa.items()]
    ENV.write_text("\n".join(baris) + "\n", encoding="utf-8")

    # Supaya perubahan langsung dipakai proses ini (dashboard & pipeline baru).
    load_dotenv(ENV, override=True)
    return True, f"{len(bersih)} setelan disimpan ke .env."


def uji_telegram(token: str = "", chat: str = "") -> tuple[bool, str]:
    """Kirim satu pesan uji. Dipakai untuk memastikan token dan chat id benar
    sebelum mengandalkan Telegram saat produksi berjalan berjam-jam."""
    token = (token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (chat or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        return False, "Token atau chat id belum diisi."
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": "✅ Uji koneksi AI Academy berhasil. Gate akan dikirim ke chat ini.",
    }).encode()
    try:
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20) as r:
            hasil = json.loads(r.read().decode("utf-8"))
        if hasil.get("ok"):
            return True, "Pesan uji terkirim. Cek Telegram Anda."
        return False, f"Telegram menolak: {hasil.get('description', '?')}"
    except urllib.error.HTTPError as e:
        rinci = e.read().decode("utf-8", "replace")[:200]
        return False, f"HTTP {e.code} dari Telegram: {rinci}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, f"Gagal menghubungi Telegram: {e}"
